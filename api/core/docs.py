"""
API documentation module.

This module sets up Swagger UI and ReDoc with customized OpenAPI specs.
"""
from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI

from api.core.config import settings


def setup_api_docs(app: FastAPI) -> None:
    """
    Set up API documentation.
    
    Customizes OpenAPI specification for the application.
    
    Args:
        app: FastAPI application
    """
    
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
            
        openapi_schema = get_openapi(
            title="Lyo API",
            version="1.0.0",
            description="""
            # Lyo API Documentation
            
            This is the API documentation for Lyo, an AI-powered multilingual social-learning app.
            
            ## Features
            
            - User management and authentication
            - Social feed with posts, likes, and comments
            - Content recommendation and discovery
            - AI-powered learning assistance
            - Multilingual support
            - Real-time notifications
            
            ## Authentication
            
            Most endpoints require authentication using JWT tokens. To authenticate:
            
            1. Register or login to get access and refresh tokens
            2. Include the access token in the Authorization header: `Bearer {token}`
            3. Use the refresh token endpoint when the access token expires
            
            ## Rate Limiting
            
            API requests are rate-limited to protect the service. Rate limit headers are included in responses:
            
            - `X-RateLimit-Limit-Minute`: Maximum requests per minute
            - `X-RateLimit-Remaining-Minute`: Remaining requests for the current minute
            - `X-RateLimit-Limit-Day`: Maximum requests per day
            - `X-RateLimit-Remaining-Day`: Remaining requests for the current day
            
            When rate limits are exceeded, the API returns a 429 status code with a `Retry-After` header.
            """,
            routes=app.routes,
        )
        
        # Add security schemes
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter the token with the `Bearer: ` prefix, e.g. `Bearer abcde12345`."
            }
        }
        
        # Add global security requirement
        openapi_schema["security"] = [{"BearerAuth": []}]
        
        # Add contact information
        openapi_schema["info"]["contact"] = {
            "name": "Lyo API Support",
            "url": "https://lyo.app/support",
            "email": "api@lyo.app"
        }
        
        # Add terms of service
        openapi_schema["info"]["termsOfService"] = "https://lyo.app/terms"
        
        # Add license information
        openapi_schema["info"]["license"] = {
            "name": "Proprietary",
            "url": "https://lyo.app/license"
        }
        
        # Add servers based on environment
        servers = []
        
        if settings.ENVIRONMENT == "production":
            servers.append({
                "url": "https://api.lyo.app",
                "description": "Production server"
            })
        elif settings.ENVIRONMENT == "staging":
            servers.append({
                "url": "https://api.staging.lyo.app",
                "description": "Staging server"
            })
        else:
            servers.append({
                "url": "http://localhost:8000",
                "description": "Development server"
            })
        
        openapi_schema["servers"] = servers
        
        # Add media type
        openapi_schema["components"]["requestBodies"] = {
            "FileUpload": {
                "description": "File upload",
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "file": {
                                    "type": "string",
                                    "format": "binary"
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Add common responses
        openapi_schema["components"]["responses"] = {
            "NotFound": {
                "description": "The specified resource was not found",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "not_found"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Resource not found"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 404
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "ValidationError": {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "validation_error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Validation error"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 422
                                        },
                                        "errors": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "loc": {
                                                        "type": "array",
                                                        "items": {
                                                            "oneOf": [
                                                                {"type": "string"},
                                                                {"type": "integer"}
                                                            ]
                                                        },
                                                        "example": ["body", "email"]
                                                    },
                                                    "msg": {
                                                        "type": "string",
                                                        "example": "Invalid email format"
                                                    },
                                                    "type": {
                                                        "type": "string",
                                                        "example": "value_error.email"
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "Unauthorized": {
                "description": "Authentication credentials were missing or incorrect",
                "headers": {
                    "WWW-Authenticate": {
                        "schema": {
                            "type": "string",
                            "example": "Bearer"
                        }
                    }
                },
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "unauthorized"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Not authenticated"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 401
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "Forbidden": {
                "description": "The server understood the request, but the user doesn't have necessary permissions",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "forbidden"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Permission denied"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 403
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "TooManyRequests": {
                "description": "Too many requests have been sent in a given amount of time",
                "headers": {
                    "Retry-After": {
                        "schema": {
                            "type": "integer",
                            "example": 60
                        }
                    }
                },
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "too_many_requests"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Rate limit exceeded"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 429
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "InternalServerError": {
                "description": "An unexpected error occurred",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "internal_server_error"
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "An unexpected error occurred"
                                        },
                                        "status": {
                                            "type": "integer",
                                            "example": 500
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    # Set custom OpenAPI function
    app.openapi = custom_openapi
