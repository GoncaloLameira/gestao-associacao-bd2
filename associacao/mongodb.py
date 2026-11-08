"""
MongoDB Service for Logging and Statistics
Sistema de Gestão de Associações - BD2
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MongoDBService:
    """
    Service class for MongoDB operations.
    Handles connection management and provides methods for logging and statistics.
    """

    _instance: Optional['MongoDBService'] = None
    _client: Optional[MongoClient] = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._connect()

    def _connect(self):
        """Establish connection to MongoDB."""
        try:
            mongo_config = settings.MONGODB
            host = mongo_config.get('HOST', 'localhost')
            port = mongo_config.get('PORT', 27017)
            db_name = mongo_config.get('DB', 'gestao_associacao_logs')
            username = mongo_config.get('USERNAME', '')
            password = mongo_config.get('PASSWORD', '')

            # Build connection URI
            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource=admin"
            else:
                uri = f"mongodb://{host}:{port}/{db_name}"

            self._client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )

            # Test connection
            self._client.admin.command('ping')
            self._db = self._client[db_name]

            # Create indexes for performance
            self._create_indexes()

            logger.info(f"MongoDB connected successfully to {host}:{port}/{db_name}")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB connection failed: {e}. Running without MongoDB.")
            self._client = None
            self._db = None
        except Exception as e:
            logger.error(f"Unexpected MongoDB error: {e}")
            self._client = None
            self._db = None

    def _create_indexes(self):
        """Create indexes for better query performance."""
        if self._db is None:
            return

        try:
            # Indexes for audit_log collection
            self._db.audit_log.create_index([("timestamp", -1)])
            self._db.audit_log.create_index([("user_id", 1), ("timestamp", -1)])
            self._db.audit_log.create_index([("action", 1), ("timestamp", -1)])
            self._db.audit_log.create_index([("entity_type", 1), ("entity_id", 1)])
            self._db.audit_log.create_index([("association_id", 1), ("timestamp", -1)])

            # Indexes for statistics collection
            self._db.statistics.create_index([("metric_name", 1), ("timestamp", -1)])
            self._db.statistics.create_index([("entity_type", 1), ("timestamp", -1)])

            # Indexes for user_activity collection
            self._db.user_activity.create_index([("user_id", 1), ("timestamp", -1)])
            self._db.user_activity.create_index([("session_id", 1), ("timestamp", -1)])

        except Exception as e:
            logger.warning(f"Failed to create MongoDB indexes: {e}")

    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        return self._client is not None and self._db is not None

    def get_db(self):
        """Get the database instance."""
        return self._db

    # ==========================================
    # AUDIT LOGGING
    # ==========================================

    def log_audit(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        user_type: Optional[str] = None,  # 'direcao' or 'associado'
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        association_id: Optional[int] = None,
    ) -> bool:
        """
        Log an audit trail entry.

        Args:
            action: Action performed (create, read, update, delete, login, logout, etc.)
            entity_type: Type of entity (associado, quota, pagamento, etc.)
            entity_id: ID of the entity affected
            user_id: ID of the user who performed the action
            user_type: Type of user (direcao or associado)
            details: Additional details about the action
            ip_address: IP address of the user
            user_agent: User agent string
            success: Whether the action was successful
            error_message: Error message if action failed

        Returns:
            True if logged successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "user_id": user_id,
                "user_type": user_type,
                "details": details or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "error_message": error_message,
                "association_id": association_id,
            }

            self._db.audit_log.insert_one(doc)
            return True

        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
            return False

    def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        skip: int = 0,
        association_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with optional filters.
        """
        if not self.is_connected():
            return []

        try:
            query = {}

            if entity_type:
                query["entity_type"] = entity_type
            if entity_id is not None:
                query["entity_id"] = entity_id
            if user_id is not None:
                query["user_id"] = user_id
            if action:
                query["action"] = action
            if association_id is not None:
                query["association_id"] = association_id
            if start_date or end_date:
                query["timestamp"] = {}
                if start_date:
                    query["timestamp"]["$gte"] = start_date
                if end_date:
                    query["timestamp"]["$lte"] = end_date

            limit = max(1, min(int(limit), 500))
            skip = max(0, int(skip))
            cursor = self._db.audit_log.find(query).sort("timestamp", -1).skip(skip).limit(limit)
            return list(cursor)

        except Exception as e:
            logger.error(f"Failed to retrieve audit logs: {e}")
            return []

    # ==========================================
    # STATISTICS
    # ==========================================

    def record_statistic(
        self,
        metric_name: str,
        value: float,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record a statistic/metric value.

        Args:
            metric_name: Name of the metric (e.g., 'total_associados', 'quotas_em_divida')
            value: Numeric value of the metric
            entity_type: Optional entity type for context
            entity_id: Optional entity ID for context
            metadata: Additional metadata

        Returns:
            True if recorded successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "metric_name": metric_name,
                "value": value,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata or {}
            }

            self._db.statistics.insert_one(doc)
            return True

        except Exception as e:
            logger.error(f"Failed to record statistic: {e}")
            return False

    def get_statistics(
        self,
        metric_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve statistics with optional filters.
        """
        if not self.is_connected():
            return []

        try:
            query = {}

            if metric_name:
                query["metric_name"] = metric_name
            if entity_type:
                query["entity_type"] = entity_type
            if start_date or end_date:
                query["timestamp"] = {}
                if start_date:
                    query["timestamp"]["$gte"] = start_date
                if end_date:
                    query["timestamp"]["$lte"] = end_date

            cursor = self._db.statistics.find(query).sort("timestamp", -1).limit(limit)
            return list(cursor)

        except Exception as e:
            logger.error(f"Failed to retrieve statistics: {e}")
            return []

    def get_latest_statistics(self, metric_names: List[str]) -> Dict[str, Any]:
        """
        Get the latest value for multiple metrics.
        """
        if not self.is_connected():
            return {}

        try:
            result = {}
            for metric_name in metric_names:
                doc = self._db.statistics.find_one(
                    {"metric_name": metric_name},
                    sort=[("timestamp", -1)]
                )
                if doc:
                    result[metric_name] = doc.get("value")
            return result

        except Exception as e:
            logger.error(f"Failed to get latest statistics: {e}")
            return {}

    # ==========================================
    # USER ACTIVITY
    # ==========================================

    def log_user_activity(
        self,
        user_id: int,
        user_type: str,  # 'direcao' or 'associado'
        action: str,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log user activity for session tracking and analytics.
        """
        if not self.is_connected():
            return False

        try:
            doc = {
                "timestamp": datetime.utcnow(),
                "user_id": user_id,
                "user_type": user_type,
                "action": action,
                "session_id": session_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "details": details or {}
            }

            self._db.user_activity.insert_one(doc)
            return True

        except Exception as e:
            logger.error(f"Failed to log user activity: {e}")
            return False

    def get_user_sessions(
        self,
        user_id: int,
        user_type: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get user sessions/activity history.
        """
        if not self.is_connected():
            return []

        try:
            cursor = self._db.user_activity.find(
                {"user_id": user_id, "user_type": user_type}
            ).sort("timestamp", -1).limit(limit)
            return list(cursor)

        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    # ==========================================
    # AGGREGATION PIPELINES FOR DASHBOARDS
    # ==========================================

    def get_dashboard_stats(self, id_associacao: int) -> Dict[str, Any]:
        """
        Get aggregated statistics for the dashboard.
        """
        if not self.is_connected():
            return {}

        try:
            # This would use aggregation pipelines for complex stats
            # For now, return empty dict - can be expanded
            return {}

        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            return {}

    def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")


# Singleton instance
mongodb_service = MongoDBService()


# Convenience functions for easy use in views
def log_audit(
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    user_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    association_id: Optional[int] = None,
) -> bool:
    """Convenience function to log audit entries."""
    return mongodb_service.log_audit(
        action, entity_type, entity_id, user_id, user_type,
        details, ip_address, user_agent, success, error_message, association_id
    )


def get_audit_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    skip: int = 0,
    association_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve audit entries using the supplied filters."""
    return mongodb_service.get_audit_logs(
        entity_type, entity_id, user_id, action, start_date, end_date,
        limit, skip, association_id,
    )


def log_user_activity(
    user_id: int,
    user_type: str,
    action: str,
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """Convenience function to log user activity."""
    return mongodb_service.log_user_activity(
        user_id, user_type, action, session_id, ip_address, user_agent, details
    )


def record_statistic(
    metric_name: str,
    value: float,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """Convenience function to record statistics."""
    return mongodb_service.record_statistic(
        metric_name, value, entity_type, entity_id, metadata
    )
