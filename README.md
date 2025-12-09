# Smart Content Recommendations Engine

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Async-336791.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)

A backend recommendation engine built with **FastAPI** and **Async SQLAlchemy**.
This project was built to explore modern backend architecture, microservices patterns, and recommendation algorithms.

## 🎯 Project Overview

This system provides personalized content recommendations using a hybrid approach. It combines multiple strategies to deliver relevant content to users based on their interactions and preferences.

### Key Features

*   **Hybrid Recommendation Engine**: Combines Content-Based and Collaborative Filtering.
*   **Trending System**: Identifies "Hot" and "Viral" content in real-time.
*   **Async Architecture**: Fully asynchronous database operations for high performance.
*   **Clean Code**: Type-hinted (MyPy), tested (Pytest), and formatted (Black).
*   **Containerized**: Docker support for easy deployment.

## 🛠️ Tech Stack

*   **Framework**: FastAPI
*   **Database**: PostgreSQL (with AsyncPG)
*   **ORM**: SQLAlchemy 2.0 (Async)
*   **Validation**: Pydantic V2
*   **Testing**: Pytest & AsyncIO
*   **Tools**: Docker, Black, Isort

## 🚀 Getting Started

### Prerequisites

*   Python 3.11+
*   Docker (optional, for database)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/smart-content-recommendations.git
    cd smart-content-recommendations
    ```

2.  **Set up Virtual Environment**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    # source venv/bin/activate  # Linux/Mac
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run with Docker (Recommended)**
    ```bash
    docker-compose up -d
    ```
    *Or run locally with SQLite for testing:*
    ```powershell
    $env:DATABASE_URL="sqlite+aiosqlite:///./dev.db"; uvicorn app.main:app --reload
    ```

5.  **Access the API**
    *   Swagger UI: http://localhost:8000/docs
    *   ReDoc: http://localhost:8000/redoc

## 🧪 Testing

The project includes unit and integration tests.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 📂 Project Structure

```
smart-content-recommendations/
├── app/
│   ├── algorithms/    # Recommendation logic (Hybrid, Content-based)
│   ├── api/          # API Routes
│   ├── core/         # Config & Security
│   ├── models/       # Database Models
│   ├── services/     # Business Logic
│   └── main.py       # Entry point
├── tests/            # Test suite
├── scripts/          # Helper scripts (seeding, health check)
└── docs/             # Documentation
```

## ☁️ Deployment & Cloud

This project is designed with production deployment in mind.

*   **Docker**: Fully containerized application with `Dockerfile` and `docker-compose`.
*   **AWS Infrastructure**: Includes CloudFormation templates for deploying to AWS ECS (Elastic Container Service).
*   **Infrastructure as Code**: See `aws/` directory for infrastructure definitions.

### Documentation

Detailed guides are available in the `docs/` directory:

*   [📖 API Usage Guide](docs/USAGE_GUIDE.md) - How to use the endpoints.
*   [🐳 Docker Setup](docs/DOCKER_SETUP.md) - Running with containers.
*   [☁️ AWS Deployment](docs/AWS_DEPLOYMENT_GUIDE.md) - Deploying to the cloud.
*   [📈 Tracking Guide](docs/RECOMMENDATION_TRACKING_GUIDE.md) - Monitoring performance.

## 📄 License

This project is open source and available under the MIT License.