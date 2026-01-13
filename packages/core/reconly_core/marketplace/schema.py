"""Bundle schema definition for feed marketplace.

Defines the JSON schema for feed bundles (v1.0).
"""

BUNDLE_SCHEMA_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Reconly Feed Bundle",
    "description": "Portable feed configuration bundle for Reconly marketplace",
    "type": "object",
    "required": ["schema_version", "bundle"],
    "properties": {
        "schema_version": {
            "type": "string",
            "const": "1.0",
            "description": "Bundle schema version"
        },
        "bundle": {
            "type": "object",
            "required": ["id", "name", "version", "sources"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": "^[a-z0-9-]+$",
                    "description": "Bundle slug identifier (kebab-case)"
                },
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 255,
                    "description": "Human-readable bundle name"
                },
                "description": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Bundle description"
                },
                "version": {
                    "type": "string",
                    "pattern": "^\\d+\\.\\d+\\.\\d+$",
                    "description": "Semantic version (e.g., 1.0.0)"
                },
                "author": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "github": {"type": "string"},
                        "email": {"type": "string", "format": "email"}
                    }
                },
                "category": {
                    "type": "string",
                    "enum": ["news", "finance", "tech", "science", "entertainment", "sports", "business", "other"],
                    "description": "Bundle category"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                    "description": "Bundle tags for discovery"
                },
                "language": {
                    "type": "string",
                    "pattern": "^[a-z]{2}$",
                    "description": "Primary language code (e.g., en, de)"
                },
                "sources": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "type", "url"],
                        "properties": {
                            "name": {"type": "string", "minLength": 1, "maxLength": 255},
                            "type": {
                                "type": "string",
                                "enum": ["rss", "youtube", "website", "blog", "podcast"]
                            },
                            "url": {"type": "string", "format": "uri"},
                            "config": {
                                "type": "object",
                                "description": "Type-specific source configuration"
                            },
                            "default_language": {"type": "string"},
                            "include_keywords": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "exclude_keywords": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "filter_mode": {
                                "type": "string",
                                "enum": ["title_only", "content", "both"]
                            },
                            "use_regex": {"type": "boolean"}
                        }
                    }
                },
                "prompt_template": {
                    "type": "object",
                    "required": ["name", "system_prompt", "user_prompt_template"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 255},
                        "description": {"type": "string"},
                        "system_prompt": {"type": "string"},
                        "user_prompt_template": {"type": "string"},
                        "language": {"type": "string"},
                        "target_length": {"type": "integer", "minimum": 10, "maximum": 2000}
                    }
                },
                "report_template": {
                    "type": "object",
                    "required": ["name", "format", "template_content"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 255},
                        "description": {"type": "string"},
                        "format": {
                            "type": "string",
                            "enum": ["markdown", "html", "text"]
                        },
                        "template_content": {"type": "string"}
                    }
                },
                "schedule": {
                    "type": "object",
                    "properties": {
                        "cron": {
                            "type": "string",
                            "description": "Cron expression (e.g., '0 8 * * *' for daily 8 AM)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Human-readable schedule description"
                        }
                    }
                },
                "output_config": {
                    "type": "object",
                    "properties": {
                        "db": {"type": "boolean", "default": True},
                        "email": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "recipients": {
                                    "type": "array",
                                    "items": {"type": "string", "format": "email"}
                                }
                            }
                        }
                    }
                },
                "digest_mode": {
                    "type": "string",
                    "enum": ["individual", "per_source", "all_sources"],
                    "default": "individual"
                }
            }
        },
        "compatibility": {
            "type": "object",
            "properties": {
                "min_reconly_version": {
                    "type": "string",
                    "pattern": "^\\d+\\.\\d+\\.\\d+$",
                    "description": "Minimum Reconly version required"
                },
                "required_features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required Reconly features (e.g., ['ollama', 'email'])"
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "license": {"type": "string"},
                "homepage": {"type": "string", "format": "uri"},
                "repository": {"type": "string", "format": "uri"}
            }
        }
    }
}
