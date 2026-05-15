from blueprints.scan_bp import bp as scan_blueprint
from blueprints.audit_logs_bp import bp as audit_logs_blueprint
from blueprints.sign_in_logs_bp import bp as sign_in_logs_blueprint
from blueprints.directory_data_bp import bp as directory_data_blueprint
from blueprints.identity_profiles_bp import bp as identity_profiles_blueprint

__all__ = [
    "scan_blueprint",
    "audit_logs_blueprint",
    "sign_in_logs_blueprint",
    "directory_data_blueprint",
    "identity_profiles_blueprint",
]
