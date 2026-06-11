"""
responses.py
============
Helper untuk membentuk response konsisten.
"""
from datetime import datetime
from fastapi.responses import JSONResponse


def success(data=None, message="Success", status_code=200):
    return JSONResponse(status_code=status_code, content={
        "success": True, "message": message,
        "timestamp": datetime.now().isoformat(), "data": data,
    })


def error(message, status_code=400, details=None):
    return JSONResponse(status_code=status_code, content={
        "success": False, "message": message,
        "timestamp": datetime.now().isoformat(), "error": details or {},
    })
