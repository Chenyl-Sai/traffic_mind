from enum import Enum

class BusinessExceptionCode(Enum):
    COMON_EXCETION_CODE = 1,
    AUTH_EXCEPTION_CODE = 2,
    BUSINESS_EXCEPTION_CODE = 3,
    SYSTEM_EXCEPTION_CODE = 4,
    VALIDATION_EXCEPTION_CODE = 5,
    NOT_FOUND_EXCEPTION_CODE = 6,

class BusinessException(Exception):
    def __init__(self, 
                 code: BusinessExceptionCode = BusinessExceptionCode.COMON_EXCETION_CODE, 
                 error_code: int = 1,
                 message: str = "",
                 message_args: tuple | None = None):
        self.code = code
        self.error_code = error_code
        self.message = message
        self.message_args = message_args
        super().__init__(self.message)

    def __str__(self):
        if self.message_args:
            format_string = self.message.format(*self.message_args)
        else:
            format_string = self.message
        return f"BusinessException: {self.code} {format_string}"
    
    
class OpenAPIException(Exception):
    def __init__(self, 
                 code: int, 
                 message: str,
                 message_args: tuple | None = None, 
                 errors: list[dict[str, str]] | None = None):
        self.code = code
        self.message = message
        self.message_args = message_args
        self.errors = errors
        super().__init__(self.message)
        
    def __str__(self):
        if self.errors:
            return f"OpenAPIException: {self.code} {self.message} {self.errors}"
        else:
            return f"OpenAPIException: {self.code} {self.message}"

class BackgroundTaskException(Exception):
    """
    后台运行任务失败异常
    """
    def __init__(self, can_resume: bool, message: str, errors: dict = None):
        self.can_resume = can_resume
        self.message = message
        self.errors = errors
        super().__init__(self.message)