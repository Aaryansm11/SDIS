# app/services/rbac.py
from typing import List, Dict, Optional, Set
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models import Role, UserRole, User
from app.core.logging import get_logger

logger = get_logger(__name__)

class RBACService:
    """Role-Based Access Control service"""
    
    # Default permissions
    DEFAULT_PERMISSIONS = {
        'admin': [
            'tenant:manage',
            'user:create', 'user:read', 'user:update', 'user:delete',
            'document:upload', 'document:read', 'document:delete',
            'search:execute', 'summarize:execute',
            'audit:read', 'reindex:trigger'
        ],
        'editor': [
            'document:upload', 'document:read', 'document:delete',
            'search:execute', 'summarize:execute'
        ],
        'viewer': [
            'document:read', 'search:execute', 'summarize:execute'
        ],
        'auditor': [
            'document:read', 'search:execute', 'audit:read'
        ]
    }
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_role(self, tenant_id: str, role_name: str, 
                   permissions: Optional[List[str]] = None) -> Dict:
        """Create a new role for a tenant"""
        
        # Use default permissions if none provided
        if permissions is None:
            permissions = self.DEFAULT_PERMISSIONS.get(role_name.lower(), [])
        
        # Check if role already exists
        existing_role = self.db.query(Role).filter(
            Role.tenant_id == tenant_id,
            Role.name == role_name
        ).first()
        
        if existing_role:
            raise ValueError(f"Role '{role_name}' already exists for tenant")
        
        # Create role
        role = Role(
            name=role_name,
            permissions=permissions,
            tenant_id=tenant_id,
            description=f"Default {role_name} role"
        )
        
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        
        logger.info(f"Created role '{role_name}' for tenant {tenant_id}")
        
        return {
            'role_id': str(role.id),
            'name': role.name,
            'permissions': role.permissions,
            'tenant_id': str(role.tenant_id)
        }
    
    def assign_role(self, user_id: str, tenant_id: str, role_name: str) -> None:
        """Assign a role to a user"""
        
        # Find the role
        role = self.db.query(Role).filter(
            Role.tenant_id == tenant_id,
            Role.name == role_name
        ).first()
        
        if not role:
            raise ValueError(f"Role '{role_name}' not found for tenant")
        
        # Check if assignment already exists
        existing = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id
        ).first()
        
        if existing:
            logger.warning(f"User {user_id} already has role {role_name}")
            return
        
        # Create assignment
        user_role = UserRole(
            user_id=user_id,
            role_id=role.id
        )
        
        self.db.add(user_role)
        self.db.commit()
        
        logger.info(f"Assigned role '{role_name}' to user {user_id}")
    
    def check_permission(self, user_id: str, tenant_id: str, permission: str) -> bool:
        """Check if user has a specific permission"""
        
        # Get user's roles and their permissions
        user_permissions = self.get_user_permissions(user_id, tenant_id)
        return permission in user_permissions
    
    def get_user_permissions(self, user_id: str, tenant_id: str) -> Set[str]:
        """Get all permissions for a user in a tenant"""
        
        permissions = set()
        
        # Query user roles and permissions
        user_roles = (
            self.db.query(UserRole, Role)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .filter(Role.tenant_id == tenant_id)
            .all()
        )
        
        for user_role, role in user_roles:
            if role.permissions:
                permissions.update(role.permissions)
        
        return permissions
    
    def get_user_roles(self, user_id: str, tenant_id: str) -> List[Dict]:
        """Get all roles for a user in a tenant"""
        
        roles = (
            self.db.query(Role)
            .join(UserRole, Role.id == UserRole.role_id)
            .filter(UserRole.user_id == user_id)
            .filter(Role.tenant_id == tenant_id)
            .all()
        )
        
        return [
            {
                'role_id': str(role.id),
                'name': role.name,
                'permissions': role.permissions,
                'description': role.description
            }
            for role in roles
        ]
    
    def create_default_roles(self, tenant_id: str) -> List[Dict]:
        """Create default roles for a new tenant"""
        
        created_roles = []
        
        for role_name, permissions in self.DEFAULT_PERMISSIONS.items():
            try:
                role_data = self.create_role(tenant_id, role_name, permissions)
                created_roles.append(role_data)
            except ValueError as e:
                logger.warning(f"Role creation failed: {e}")
        
        return created_roles
    
    def remove_role(self, user_id: str, tenant_id: str, role_name: str) -> bool:
        """Remove a role from a user"""
        
        # Find the role
        role = self.db.query(Role).filter(
            Role.tenant_id == tenant_id,
            Role.name == role_name
        ).first()
        
        if not role:
            return False
        
        # Find and delete assignment
        assignment = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id
        ).first()
        
        if assignment:
            self.db.delete(assignment)
            self.db.commit()
            logger.info(f"Removed role '{role_name}' from user {user_id}")
            return True
        
        return False

# Module-level functions
def create_role(db: Session, tenant_id: str, role_name: str, 
               permissions: Optional[List[str]] = None) -> Dict:
    """Module-level function to create a role"""
    service = RBACService(db)
    return service.create_role(tenant_id, role_name, permissions)

def assign_role(db: Session, user_id: str, tenant_id: str, role_name: str) -> None:
    """Module-level function to assign a role"""
    service = RBACService(db)
    return service.assign_role(user_id, tenant_id, role_name)

def check_permission(db: Session, user_id: str, tenant_id: str, permission: str) -> bool:
    """Module-level function to check permission"""
    service = RBACService(db)
    return service.check_permission(user_id, tenant_id, permission)