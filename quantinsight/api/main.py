from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from quantinsight.schemas import ErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(
        title="ScribeGraph Core API",
        description="FastAPI service for ScribeGraph research paper ingestion and agentic query loop.",
        version="0.1.0",
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Structured Error Handling Exception Handlers

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(f"Validation error on {request.url.path}: {exc}")
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code="UNPROCESSABLE_ENTITY",
                message="Request validation failed.",
                details={"errors": exc.errors()}
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_resp.model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning(f"HTTP error {exc.status_code} on {request.url.path}: {exc.detail}")
        # Map status code to string error code
        code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
        elif exc.status_code == status.HTTP_400_BAD_REQUEST:
            code = "BAD_REQUEST"
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = "FORBIDDEN"

        error_resp = ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=str(exc.detail),
                details={"status_code": exc.status_code}
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_resp.model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected error occurred. Please check logs.",
                details={"error_class": exc.__class__.__name__}
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_resp.model_dump(),
        )

    # Routes
    @app.get("/", tags=["General"])
    async def root():
        return {
            "app": "ScribeGraph Core API",
            "version": "0.1.0",
            "status": "healthy"
        }

    @app.get("/health", tags=["General"])
    async def health():
        return {
            "status": "healthy"
        }

    return app

app = create_app()
