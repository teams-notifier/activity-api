#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

import dotenv

dotenv.load_dotenv()
""" Bot Configuration """


class DefaultConfig:
    """Bot Configuration"""

    PORT = int(os.environ.get("PORT", "3980"))
    APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
    APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
    APP_TYPE = os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("MICROSOFT_APP_TENANT_ID", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
