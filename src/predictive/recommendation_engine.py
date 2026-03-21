"""
Product Recommendation Engine
─────────────────────────────────────────────────────────────────────────────
Collaborative Filtering using:
- ALS (Alternating Least Squares) Matrix Factorization
- Item-based collaborative filtering
- Hybrid with content-based features
"""
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

from config.settings import PROCESSED_DIR, MODELS_DIR, REPORTS_DIR

try:
    from implicit.als import AlternatingLeastSquares
    from implicit.recommender import ModelFitException
    IMPLICIT_AVAILABLE = True
except ImportError:
    IMPLICIT_AVAILABLE = False
    print("Warning: implicit package not installed. Using simplified CF implementation.")


class ProductRecommender:
    """
    Product recommendation using collaborative filtering.
    
    Supports:
    - ALS Matrix Factorization (implicit feedback)
    - Item-item collaborative filtering
    - User-based recommendations
    - Hybrid scoring with popularity
    """
    
    def __init__(self, n_factors: int = 50, regularization: float = 0.01,
                 iterations: int = 30):
        self.n_factors = n_factors
        self.regularization = regularization
        self.iterations = iterations
        self.model = None
        self.user_item_matrix = None
        self.user_mapping = {}
        self.item_mapping = {}
        self.reverse_user_mapping = {}
        self.reverse_item_mapping = {}
        self.item_features = None
        self.item_similarity = None
        
    def prepare_data(self, transactions_df: pd.DataFrame,
                     user_col: str = 'customer_id',
                     item_col: str = 'product_id',
                     interaction_col: str = 'quantity') -> pd.DataFrame:
        """
        Prepare transaction data for collaborative filtering.
        """
        data = transactions_df[[user_col, item_col, interaction_col]].copy()
        
        # Aggregate interactions per user-item pair
        data = data.groupby([user_col, item_col])[interaction_col].sum().reset_index()
        
        # Create mappings
        users = data[user_col].unique()
        items = data[item_col].unique()
        
        self.user_mapping = {u: i for i, u in enumerate(users)}
        self.item_mapping = {it: i for i, it in enumerate(items)}
        self.reverse_user_mapping = {i: u for u, i in self.user_mapping.items()}
        self.reverse_item_mapping = {i: it for it, i in self.item_mapping.items()}
        
        # Map to indices
        data['user_idx'] = data[user_col].map(self.user_mapping)
        data['item_idx'] = data[item_col].map(self.item_mapping)
        
        # Remove unmapped entries
        data = data.dropna(subset=['user_idx', 'item_idx'])
        data['user_idx'] = data['user_idx'].astype(int)
        data['item_idx'] = data['item_idx'].astype(int)
        
        return data
    
    def create_user_item_matrix(self, data: pd.DataFrame) -> np.ndarray:
        """Create user-item interaction matrix."""
        n_users = data['user_idx'].max() + 1
        n_items = data['item_idx'].max() + 1
        
        matrix = np.zeros((n_users, n_items))
        
        for _, row in data.iterrows():
            matrix[int(row['user_idx']), int(row['item_idx'])] = row[data.columns[3]]  # interaction value
        
        return matrix
    
    def fit_als(self, data: pd.DataFrame):
        """Fit ALS model using implicit library."""
        if not IMPLICIT_AVAILABLE:
            print("ALS not available, falling back to item-based CF")
            return self.fit_item_cf(data)
        
        # Create sparse matrix
        user_item_matrix = self.create_user_item_matrix(data)
        self.user_item_matrix = user_item_matrix
        
        # Convert to CSR for implicit library
        from scipy.sparse import csr_matrix
        sparse_matrix = csr_matrix(user_item_matrix)
        
        # Fit ALS model
        self.model = AlternatingLeastSquares(
            factors=self.n_factors,
            regularization=self.regularization,
            iterations=self.iterations,
            use_native=True,
            use_cg=True,
            use_gpu=False,
            random_state=42
        )
        
        self.model.fit(sparse_matrix)
        
        return self.model
    
    def fit_item_cf(self, data: pd.DataFrame):
        """Fit item-based collaborative filtering model."""
        user_item_matrix = self.create_user_item_matrix(data)
        self.user_item_matrix = user_item_matrix
        
        # Calculate item-item similarity
        # Transpose to get items as rows
        item_matrix = user_item_matrix.T
        
        # Handle sparse data with regularization
        norm = np.sqrt((item_matrix ** 2).sum(axis=1))
        norm[norm == 0] = 1  # Avoid division by zero
        
        normalized = item_matrix / norm[:, np.newaxis]
        
        # Cosine similarity
        self.item_similarity = np.dot(normalized, normalized.T)
        
        # Ensure diagonal is 1
        np.fill_diagonal(self.item_similarity, 1)
        
        return self.item_similarity
    
    def fit(self, transactions_df: pd.DataFrame,
            user_col: str = 'customer_id',
            item_col: str = 'product_id',
            interaction_col: str = 'quantity',
            use_als: bool = True):
        """
        Fit the recommendation model.
        
        Parameters
        ----------
        transactions_df : pd.DataFrame
            Transaction data
        user_col : str
            Customer ID column name
        item_col : str
            Product ID column name
        interaction_col : str
            Interaction strength column (quantity, amount, etc.)
        use_als : bool
            Whether to use ALS (if available) or fall back to item-CF
        """
        print("Preparing data...")
        data = self.prepare_data(transactions_df, user_col, item_col, interaction_col)
        print(f"Created matrix with {len(self.user_mapping)} users and {len(self.item_mapping)} items")
        
        if use_als and IMPLICIT_AVAILABLE:
            print("Fitting ALS model...")
            self.fit_als(data)
        else:
            print("Fitting Item-based CF model...")
            self.fit_item_cf(data)
        
        # Store item features for hybrid recommendations
        if 'category' in transactions_df.columns:
            self._compute_item_features(transactions_df)
        
        return self
    
    def _compute_item_features(self, transactions_df: pd.DataFrame):
        """Compute item features for hybrid recommendations."""
        # Use available columns only
        agg_dict = {}
        if 'category' in transactions_df.columns:
            agg_dict['category'] = 'first'
        if 'price' in transactions_df.columns:
            agg_dict['price'] = 'mean'
        if 'quantity' in transactions_df.columns:
            agg_dict['quantity'] = 'sum'
        if 'total_amount' in transactions_df.columns:
            agg_dict['total_amount'] = 'mean'
            
        item_features = transactions_df.groupby('product_id').agg(agg_dict).reset_index()

        # One-hot encode category
        if 'category' in item_features.columns:
            categories = item_features['category'].unique()
            category_dummies = pd.get_dummies(item_features['category'], prefix='cat')
            item_features = pd.concat([item_features, category_dummies], axis=1)

        # Map to item indices
        item_features['item_idx'] = item_features['product_id'].map(self.item_mapping)
        item_features = item_features.dropna(subset=['item_idx'])

        # Store feature matrix
        feature_cols = [c for c in item_features.columns
                       if c not in ['product_id', 'category', 'item_idx']]
        self.item_features = item_features.set_index('item_idx')[feature_cols].values

        # Compute item similarity based on features
        if len(self.item_features) > 0:
            scaler = StandardScaler()
            item_features_scaled = scaler.fit_transform(self.item_features)
            self.item_feature_similarity = cosine_similarity(item_features_scaled)
        else:
            self.item_feature_similarity = None
    
    def recommend_for_user(self, customer_id, n_recommendations: int = 10,
                           exclude_purchased: bool = True,
                           hybrid_alpha: float = 0.5) -> pd.DataFrame:
        """
        Get top N recommendations for a specific user.
        
        Parameters
        ----------
        customer_id : int or str
            Customer ID
        n_recommendations : int
            Number of recommendations
        exclude_purchased : bool
            Whether to exclude already purchased items
        hybrid_alpha : float
            Weight for CF vs content-based (0.5 = equal weight)
        """
        if customer_id not in self.user_mapping:
            # Cold start: return popular items
            return self._get_popular_items(n_recommendations)
        
        user_idx = self.user_mapping[customer_id]
        
        if self.model is not None and IMPLICIT_AVAILABLE:
            # ALS recommendations
            user_vector = self.user_item_matrix[user_idx]
            purchased_indices = np.where(user_vector > 0)[0]
            
            scores = self.model.recommend(
                user_idx,
                self.user_item_matrix[user_idx],
                N=n_recommendations + len(purchased_indices),
                filter_already_liked_items=exclude_purchased
            )
            
            recommendations = pd.DataFrame({
                'item_idx': [i[0] for i in scores],
                'score': [i[1] for i in scores]
            })
            
        elif self.item_similarity is not None:
            # Item-based CF recommendations
            user_vector = self.user_item_matrix[user_idx]
            purchased_indices = np.where(user_vector > 0)[0]
            
            if len(purchased_indices) == 0:
                return self._get_popular_items(n_recommendations)
            
            # Aggregate scores from purchased items
            scores = np.zeros(self.user_item_matrix.shape[1])
            
            for purchased_idx in purchased_indices:
                scores += self.item_similarity[purchased_idx] * user_vector[purchased_idx]
            
            # Normalize by number of purchases
            scores = scores / (len(purchased_indices) + 1)
            
            # Exclude purchased items
            if exclude_purchased:
                scores[purchased_indices] = -np.inf
            
            # Get top N
            top_indices = np.argsort(scores)[::-1][:n_recommendations]
            
            recommendations = pd.DataFrame({
                'item_idx': top_indices,
                'score': scores[top_indices]
            })
        else:
            return self._get_popular_items(n_recommendations)
        
        # Map back to product IDs
        recommendations['product_id'] = recommendations['item_idx'].map(self.reverse_item_mapping)
        recommendations['customer_id'] = customer_id
        
        # Remove any NaN mappings
        recommendations = recommendations.dropna(subset=['product_id'])
        
        return recommendations.head(n_recommendations)
    
    def recommend_similar_items(self, product_id, n_recommendations: int = 10) -> pd.DataFrame:
        """Get recommendations for similar items."""
        if product_id not in self.item_mapping:
            return pd.DataFrame()
        
        item_idx = self.item_mapping[product_id]
        
        if self.item_similarity is not None:
            similarities = self.item_similarity[item_idx]
        elif self.item_feature_similarity is not None:
            similarities = self.item_feature_similarity[item_idx]
        else:
            return pd.DataFrame()
        
        # Get top N similar (excluding self)
        similar_indices = np.argsort(similarities)[::-1][1:n_recommendations + 1]
        
        recommendations = pd.DataFrame({
            'item_idx': similar_indices,
            'similarity': similarities[similar_indices]
        })
        
        recommendations['product_id'] = recommendations['item_idx'].map(self.reverse_item_mapping)
        recommendations['source_product_id'] = product_id
        
        return recommendations.dropna(subset=['product_id'])
    
    def _get_popular_items(self, n: int) -> pd.DataFrame:
        """Get most popular items (cold start fallback)."""
        if self.user_item_matrix is None:
            return pd.DataFrame()
        
        # Sum interactions across all users
        popularity = self.user_item_matrix.sum(axis=0)
        top_indices = np.argsort(popularity)[::-1][:n]
        
        return pd.DataFrame({
            'item_idx': top_indices,
            'score': popularity[top_indices],
            'product_id': [self.reverse_item_mapping.get(i) for i in top_indices]
        })
    
    def evaluate(self, data: pd.DataFrame, k: int = 10) -> dict:
        """
        Evaluate recommendation quality using leave-one-out cross-validation.
        
        Returns:
        - Precision@K
        - Recall@K
        - NDCG@K
        """
        from sklearn.model_selection import train_test_split
        
        # Split data
        train, test = train_test_split(data, test_size=0.2, random_state=42)
        
        # Refit on training data
        if self.model is not None and IMPLICIT_AVAILABLE:
            self.fit_als(train)
        else:
            self.fit_item_cf(train)
        
        # Evaluate
        precisions = []
        recalls = []
        ndcgs = []
        
        test_users = test['user_idx'].unique()
        
        for user_idx in test_users[:100]:  # Sample for speed
            # Get test items for this user
            test_items = set(test[test['user_idx'] == user_idx]['item_idx'].values)
            
            if len(test_items) == 0:
                continue
            
            # Get recommendations
            if self.model is not None and IMPLICIT_AVAILABLE:
                scores = self.model.recommend(
                    user_idx,
                    self.user_item_matrix[user_idx],
                    N=k,
                    filter_already_liked_items=True
                )
                rec_items = set([i[0] for i in scores])
            else:
                recs = self.recommend_for_user(
                    self.reverse_user_mapping.get(user_idx, -1),
                    n_recommendations=k
                )
                rec_items = set(recs['item_idx'].values)
            
            # Calculate metrics
            hits = len(rec_items & test_items)
            
            precision = hits / len(rec_items) if len(rec_items) > 0 else 0
            recall = hits / len(test_items) if len(test_items) > 0 else 0
            
            # NDCG
            dcg = sum([hits / np.log2(i + 2) for i, _ in enumerate(rec_items)])
            idcg = sum([1 / np.log2(i + 2) for i in range(min(len(test_items), k))])
            ndcg = dcg / idcg if idcg > 0 else 0
            
            precisions.append(precision)
            recalls.append(recall)
            ndcgs.append(ndcg)
        
        return {
            'precision@k': np.mean(precisions),
            'recall@k': np.mean(recalls),
            'ndcg@k': np.mean(ndcgs)
        }
    
    def save(self, path: Path = None):
        """Save model to disk."""
        if path is None:
            path = MODELS_DIR / "recommendation_model.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Don't save large matrices
        user_item_matrix = self.user_item_matrix
        item_similarity = self.item_similarity
        self.user_item_matrix = None
        self.item_similarity = None
        
        joblib.dump(self, path)
        
        # Restore
        self.user_item_matrix = user_item_matrix
        self.item_similarity = item_similarity
        
        print(f"Model saved to {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> 'ProductRecommender':
        """Load model from disk."""
        if path is None:
            path = MODELS_DIR / "recommendation_model.pkl"
        return joblib.load(path)


def train_recommendation_model():
    """
    Main function to train recommendation model.
    """
    print("Training product recommendation model...")
    
    # Load transaction data
    txn_path = PROCESSED_DIR / "transactions.parquet"
    if not txn_path.exists():
        # Try raw directory
        txn_path = Path("data/raw/transactions.parquet")
    
    if not txn_path.exists():
        raise FileNotFoundError(f"Transaction data not found")
    
    df = pd.read_parquet(txn_path)
    print(f"Loaded {len(df)} transactions")
    
    # Train model
    recommender = ProductRecommender(
        n_factors=50,
        regularization=0.01,
        iterations=30
    )
    recommender.fit(df, use_als=IMPLICIT_AVAILABLE)
    
    # Evaluate
    if len(df) > 1000:
        print("\nEvaluating model...")
        data = recommender.prepare_data(df)
        metrics = recommender.evaluate(data)
        print(f"Precision@10: {metrics['precision@k']:.4f}")
        print(f"Recall@10: {metrics['recall@k']:.4f}")
        print(f"NDCG@10: {metrics['ndcg@k']:.4f}")
    
    # Generate sample recommendations
    print("\nSample recommendations:")
    sample_customers = list(recommender.user_mapping.keys())[:5]
    
    for customer_id in sample_customers:
        recs = recommender.recommend_for_user(customer_id, n_recommendations=5)
        if len(recs) > 0:
            print(f"\nCustomer {customer_id}:")
            print(recs[['product_id', 'score']].to_string())
    
    # Save model
    recommender.save()
    
    # Save all recommendations for dashboard
    print("\nGenerating recommendations for all customers...")
    all_recommendations = []
    
    for customer_id in list(recommender.user_mapping.keys())[:1000]:  # Limit for speed
        recs = recommender.recommend_for_user(customer_id, n_recommendations=10)
        all_recommendations.append(recs)
    
    if all_recommendations:
        all_recs_df = pd.concat(all_recommendations, ignore_index=True)
        output_path = PROCESSED_DIR / "product_recommendations.parquet"
        all_recs_df.to_parquet(output_path, index=False)
        print(f"All recommendations saved to {output_path}")
    
    return recommender


if __name__ == "__main__":
    train_recommendation_model()
