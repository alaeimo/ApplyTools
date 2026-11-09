"""Extension app — Chrome Extension integration for ApplyTools.

Provides:
- ExtensionToken model (per-user API token for the browser extension)
- ExtensionTokenAuthentication (DRF auth class)
- /api/v1/ext/* endpoints (selectors, positions/bulk, by-url lookup)
"""
default_app_config = 'apps.extension.apps.ExtensionConfig'
