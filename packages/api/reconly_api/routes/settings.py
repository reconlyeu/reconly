"""Settings API routes."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional

from reconly_api.dependencies import get_db
from reconly_api.schemas.settings import (
    SettingsResponse, SettingValue, SettingsUpdateRequest,
    SettingsResetRequest, SettingsResetResponse,
    TestEmailRequest, TestEmailResponse,
)
from reconly_core.services.settings_service import SettingsService

router = APIRouter()


@router.post("/test-email", response_model=TestEmailResponse)
async def test_email(
    request: TestEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Test email configuration by sending a test email.

    Attempts to send an email using the current SMTP settings to verify
    the configuration is correct. Reads settings from SettingsService
    (DB > env > defaults).
    """
    service = SettingsService(db)

    # Get SMTP settings from SettingsService
    smtp_host = service.get("email.smtp_host")
    smtp_port = service.get("email.smtp_port")
    smtp_user = service.get("email.smtp_user")
    smtp_password = service.get("email.smtp_password")
    from_address = service.get("email.from_address")
    from_name = service.get("email.from_name")

    # Validate required settings
    if not smtp_host:
        raise HTTPException(
            status_code=400,
            detail="SMTP host is not configured"
        )
    if not from_address:
        raise HTTPException(
            status_code=400,
            detail="From email address is not configured"
        )

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <{from_address}>"
        msg['To'] = request.to_email
        msg['Subject'] = request.subject

        # Add body
        msg.attach(MIMEText(request.body, 'plain'))

        # Connect to SMTP server
        if smtp_port == 465:
            # SSL
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            # TLS
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        # Login if credentials provided
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        # Send email
        server.send_message(msg)
        server.quit()

        return TestEmailResponse(
            success=True,
            message=f"Test email sent successfully to {request.to_email}"
        )

    except smtplib.SMTPAuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail=f"SMTP authentication failed: {str(e)}"
        )
    except smtplib.SMTPException as e:
        raise HTTPException(
            status_code=500,
            detail=f"SMTP error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test email: {str(e)}"
        )


@router.get("", response_model=SettingsResponse)
async def get_settings(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all settings with source indicators.

    Returns settings organized by category, with each setting showing its value,
    source (database/environment/default), and whether it's editable.

    Categories are populated dynamically from SETTINGS_REGISTRY - extensions can
    register new categories without code changes.

    Args:
        category: Optional filter by category (e.g., provider, email, fetch, rag)
    """
    service = SettingsService(db)

    if category:
        # Get settings for specific category
        settings_data = service.get_all(category)
        # Convert to SettingValue objects
        # Use key after category prefix to avoid collisions (e.g., export.obsidian.subfolder -> obsidian.subfolder)
        category_settings = {
            ".".join(key.split(".")[1:]): SettingValue(**data)
            for key, data in settings_data.items()
        }

        # For component categories, also include dynamic settings from database
        # that may not be in SETTINGS_REGISTRY
        if category in ("provider", "fetch", "export"):
            dynamic_settings = service.get_dynamic_component_settings(category)
            for key, data in dynamic_settings.items():
                short_key = ".".join(key.split(".")[1:])
                category_settings[short_key] = SettingValue(**data)

        # Return with only the requested category
        return SettingsResponse(categories={category: category_settings})

    # Get all settings by category dynamically from registry
    all_settings = service.get_by_category()

    # Convert to response format
    categories = {}
    for cat, cat_settings in all_settings.items():
        categories[cat] = {
            ".".join(key.split(".")[1:]): SettingValue(**data)
            for key, data in cat_settings.items()
        }

    # Add dynamic component settings (provider.*, fetch.*, export.*) from database
    # These may not be in SETTINGS_REGISTRY but stored via set_raw()
    for component_prefix in ("provider", "fetch", "export"):
        dynamic_settings = service.get_dynamic_component_settings(component_prefix)
        if dynamic_settings:
            if component_prefix not in categories:
                categories[component_prefix] = {}
            for key, data in dynamic_settings.items():
                short_key = ".".join(key.split(".")[1:])
                categories[component_prefix][short_key] = SettingValue(**data)

    return SettingsResponse(categories=categories)


@router.put("", response_model=dict)
async def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update multiple settings.

    Only editable settings can be modified. Non-editable settings (secrets)
    will return an error.

    Example request:
    ```json
    {
        "settings": [
            {"key": "llm.default_provider", "value": "anthropic"},
            {"key": "email.smtp_host", "value": "smtp.gmail.com"}
        ]
    }
    ```
    """
    service = SettingsService(db)
    updated = []
    errors = []

    for setting in request.settings:
        try:
            # Component settings (provider.*, fetch.*, export.*) may be dynamically
            # registered and not always in SETTINGS_REGISTRY, so use set_raw() for them
            if any(setting.key.startswith(prefix) for prefix in ("provider.", "fetch.", "export.")):
                service.set_raw(setting.key, setting.value)
            else:
                service.set(setting.key, setting.value)
            updated.append(setting.key)
        except KeyError:
            errors.append({"key": setting.key, "error": f"Unknown setting: {setting.key}"})
        except ValueError as e:
            errors.append({"key": setting.key, "error": str(e)})

    return {
        "updated": updated,
        "errors": errors,
        "message": f"Updated {len(updated)} settings" + (f", {len(errors)} errors" if errors else "")
    }


@router.post("/reset", response_model=SettingsResetResponse)
async def reset_settings(
    request: SettingsResetRequest,
    db: Session = Depends(get_db)
):
    """
    Reset settings to their environment or default values.

    Removes database overrides for the specified settings, causing them
    to fall back to environment variables or code defaults.
    """
    service = SettingsService(db)
    reset_keys = []
    not_found = []

    for key in request.keys:
        try:
            # Component settings use delete() since they may not be in SETTINGS_REGISTRY
            if any(key.startswith(prefix) for prefix in ("provider.", "fetch.", "export.")):
                if service.delete(key):
                    reset_keys.append(key)
                else:
                    not_found.append(key)
            else:
                if service.reset(key):
                    reset_keys.append(key)
                else:
                    not_found.append(key)
        except KeyError:
            not_found.append(key)

    return SettingsResetResponse(reset=reset_keys, not_found=not_found)
