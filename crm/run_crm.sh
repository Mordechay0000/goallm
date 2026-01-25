#!/bin/bash
# Run CRM server
cd "$(dirname "$0")/.."
python3 -m crm.app
