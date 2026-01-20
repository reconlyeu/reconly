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

    Returns settings organized by category (provider, email, export),
    with each setting showing its value, source (database/environment/default),
    and whether it's editable.

    Args:
        category: Optional filter by category (provider, email, export)
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
        # Return with only the requested category
        result = {
            "provider": {}, "email": {}, "export": {}, "fetch": {},
            "embedding": {}, "rag": {}, "agent": {}, "resilience": {}
        }
        result[category] = category_settings
        return SettingsResponse(**result)

    # Get all settings by category
    all_settings = service.get_by_category()

    # Convert to response format
    result = {}
    for cat, cat_settings in all_settings.items():
        result[cat] = {
            ".".join(key.split(".")[1:]): SettingValue(**data)
            for key, data in cat_settings.items()
        }

    return SettingsResponse(**result)


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
            if service.reset(key):
                reset_keys.append(key)
            else:
                not_found.append(key)
        except KeyError:
            not_found.append(key)

    return SettingsResetResponse(reset=reset_keys, not_found=not_found)
