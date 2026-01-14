#!/bin/bash
# Security audit script using pip-audit
#
# This script runs a security audit on Python dependencies using pip-audit.
# It checks for known vulnerabilities in installed packages.
#
# Usage:
#   ./scripts/security-audit.sh           # Run audit with strict mode
#   ./scripts/security-audit.sh --fix     # Attempt to fix vulnerabilities
#
# Requirements:
#   pip install pip-audit
#
# Exit codes:
#   0 - No vulnerabilities found
#   1 - Vulnerabilities found or audit failed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  Reconly Security Audit"
echo "========================================"
echo ""

# Check if pip-audit is installed
if ! command -v pip-audit &> /dev/null; then
    echo -e "${RED}Error: pip-audit is not installed${NC}"
    echo "Install it with: pip install pip-audit"
    exit 1
fi

# Run the audit
echo "Running pip-audit..."
echo ""

# Temporarily disable exit-on-error to capture the exit code
set +e

if [ "$1" == "--fix" ]; then
    echo -e "${YELLOW}Attempting to fix vulnerabilities...${NC}"
    pip-audit --fix --progress-spinner off
else
    pip-audit --strict --progress-spinner off
fi

AUDIT_EXIT_CODE=$?
set -e

echo ""
if [ $AUDIT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}No vulnerabilities found!${NC}"
else
    echo -e "${RED}Vulnerabilities detected. Please review and update affected packages.${NC}"
fi

exit $AUDIT_EXIT_CODE
