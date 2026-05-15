"""Azure Durable Functions app — Entra Permissions scan orchestration.

Logging: The Azure Functions Python runtime automatically forwards Python
``logging`` output to Application Insights when APPLICATIONINSIGHTS_CONNECTION_STRING
is set.  We configure the root logger at INFO so all module-level loggers
(utils.graph_client, blueprints.*, etc.) are captured.  The same App Insights
resource is shared with the backend Container App for unified debugging.
"""

import json
import logging
import os

import azure.functions as func
import azure.durable_functions as df

from blueprints import (
    scan_blueprint,
    audit_logs_blueprint,
    sign_in_logs_blueprint,
    directory_data_blueprint,
    identity_profiles_blueprint,
)

# Configure root logger — the Azure Functions host attaches an App Insights
# handler automatically; we just need to ensure our loggers emit at INFO.
logging.basicConfig(level=logging.INFO)

# Reduce noise from chatty libraries
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)

app.register_functions(scan_blueprint)
app.register_functions(audit_logs_blueprint)
app.register_functions(sign_in_logs_blueprint)
app.register_functions(directory_data_blueprint)
app.register_functions(identity_profiles_blueprint)

logger.info("Function app initialized — blueprints registered")

appinsights_configured = bool(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"))
if not appinsights_configured:
    logger.warning("APPLICATIONINSIGHTS_CONNECTION_STRING not set — logs will not appear in App Insights")


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({
            "status": "ok",
            "appinsights_configured": appinsights_configured,
        }),
        mimetype="application/json",
    )
