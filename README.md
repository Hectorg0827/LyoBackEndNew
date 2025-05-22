# Lyo Backend

A production-ready, modular monolith backend for Lyo, an AI-powered multilingual social-learning application.

## Features

- **Modular Monolith Architecture**: Organized by domain functionality with clean separation of concerns
- **Multilingual Support**: Built-in internationalization for global audience
- **AI Integration**: Gemma 3 integration for personalized learning experiences
- **Multiple Database Support**: PostgreSQL for structured data, Firestore for flexible schema needs
- **Caching Layer**: Redis for performance optimization
- **Real-time Capabilities**: WebSocket support for instant notifications
- **Comprehensive Security**: JWT authentication, role-based access controls
- **Observability**: OpenTelemetry integration for monitoring and tracing

## Tech Stack

- **Web Framework**: FastAPI
- **Relational Database**: PostgreSQL with SQLModel
- **NoSQL Database**: Firestore
- **Caching**: Redis
- **AI Platform**: Gemma 3
- **Authentication**: JWT with OAuth2
- **Internationalization**: Babel
- **Testing**: Pytest with asyncio
- **Containerization**: Docker with docker-compose
- **Observability**: OpenTelemetry

## Project Structure

```
lyo-backend/
├── api/
│   ├── core/         # Core application modules
│   ├── db/           # Database connectors and utilities
│   ├── middlewares/  # Custom middleware components
│   ├── models/       # Data models and entities
│   ├── routers/      # API endpoints and route definitions
│   ├── schemas/      # Pydantic schemas for request/response
│   └── services/     # Business logic and service layer
├── tests/            # Test suite
├── .env.example      # Environment variable template
├── .env.test         # Test environment variables
├── Dockerfile        # Production Docker configuration
├── Dockerfile.test   # Testing Docker configuration
├── docker-compose.yml        # Development environment setup
├── docker-compose.test.yml   # Testing environment setup
├── requirements.txt  # Python dependencies
└── main.py           # Application entry point
```

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and docker-compose
- PostgreSQL
- Redis
- Google Cloud account (for Firestore, Pub/Sub, Storage)

### Local Development Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/lyo-backend.git
   cd lyo-backend
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. Run the application
   ```bash
   uvicorn main:app --reload
   ```

### Docker Setup

1. Build and start the containers
   ```bash
   docker-compose up --build
   ```

2. The API will be available at `http://localhost:8000`

## Testing

Run the test suite:

```bash
# Using pytest directly
pytest

# Using Docker
docker-compose -f docker-compose.test.yml up --build
```

## API Documentation

Once the application is running:

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## Deployment

### Production Considerations

- Update SECRET_KEY and other sensitive environment variables
- Set DEBUG=false
- Configure proper CORS settings
- Set up proper database credentials
- Configure telemetry endpoints
- Enable rate limiting for public endpoints

## License

[MIT](LICENSE)
