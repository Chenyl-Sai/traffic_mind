from app.core.exceptions import BusinessException, OpenAPIException, BusinessExceptionCode

from fastapi import Request, status
from fastapi.responses import JSONResponse

def init_exception_handlers(app):
    # 业务异常
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        if exc.message_args:
            format_string = exc.message.format(*exc.message_args)
        else:
            format_string = exc.message
        if exc.code == BusinessExceptionCode.COMON_EXCETION_CODE:
            status_code = status.HTTP_400_BAD_REQUEST
        elif exc.code == BusinessExceptionCode.AUTH_EXCEPTION_CODE:
            status_code = status.HTTP_401_UNAUTHORIZED
        elif exc.code == BusinessExceptionCode.BUSINESS_EXCEPTION_CODE:
            status_code = status.HTTP_400_BAD_REQUEST
        elif exc.code == BusinessExceptionCode.SYSTEM_EXCEPTION_CODE:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return JSONResponse(status_code=status_code, 
                            content={
                                "code": exc.code.value[0],
                                "success": False,
                                "has_business_error": True,
                                "error_code": exc.error_code,
                                "error_message": format_string
                                })
    
    # OpenAPI异常
    @app.exception_handler(OpenAPIException)
    async def openapi_exception_handler(request: Request, exc: OpenAPIException):
        if exc.message_args:
            format_string = exc.message.format(*exc.message_args)
        else:
            format_string = exc.message
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, 
                            content={
                                "success": False,
                                "code": exc.code,
                                "message": format_string,
                                "errors": exc.errors
                                })