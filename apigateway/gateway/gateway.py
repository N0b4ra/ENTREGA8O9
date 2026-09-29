from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response
    )
import httpx
import os
import secrets


app = FastAPI(title= "Local API Gateway")

security = HTTPBearer(
    auto_error = False
)

VAULT_ADDR = os.getenv(
    "VAULT_ADDR", "http://127.0.0.1:8200"
)

VAULT_TOKEN = os.getenv(
    "VAULT_TOKEN"
)

BACKEND_URL = "http://localhost:9000" #dastapi

if not VAULT_TOKEN:
    raise RuntimeError(
        "VAULT TOKEN no esta configurado"
    )

#Obtener Secretos

async get_gateway_secrets():
    url = (
        f"{VAULT_ADDR}"
        "/vl/secret/data/gateway"
    )
    headers = {
        "X-Vault-Token":VAULT_TOKEN
    }
    
    async with httpx.AsyncClient(
        timeout=5.0
    ) as client:
        response = await client.get(
            url,
            headers=headers
        )
        if response.status.code != 200:
            rasie HTTPException(
                status_code = 500,
                detailt="No fue posible acceder a vault"
            )
        vault_response = response.json()
        return vault_response[
            "data"
        ][
            "data"
        ]
        
async def authenticate_client(
    credentials:
        HTTPAuthorizationCredentials
        = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token requerido"
        )
    vault_secrets = (
        await get_gateway_secrets()
    )

    expected_token = vault_secrets[
        "client_token"
    ]
    recieved_token = (
        credentials.credentials
    )
    
    valid = secrets.compare.digest(
        recieved_token,
        expected_token
    )
    if not valid:
        raise HTTPException(
            status_code = 401,
            detailt = "Token Invalido"
        )
    return (
        "client_id": "student-client",
        "backend_secret": vault_secrets[
            "backend_shared_secret"
        ]
    )

# http://localhost:8000/api/productos
#@app.get("/api/productos")
#async def get_productos():
#   async with httpx.AsyncClient() as client:
#        response = await client.get(
#            f"{BACKEND_URL}/productos"  # http://localhost:9100/productos
#        )
#   return response.json()
        


#@app.get("/api/ordenes")
#async def ordenes():
#    async with httpx.AsyncClient() as client:
#        response = await client.get(
#            f"{BACKEND_URL}/ordenes"  # http://localhost:9000/ordenes
#        )
#    return response.json()




@app.api_route(
    "/api/{path:path}",
    methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE"
    ]
)
async def proxy(
    path: str,
    request: Request,
    auth=Depends(authenticate_client)
):
    target_url = (
        f"{BACKEND_URL}/{path}"
    )
    body = await request.body()
    
    gateway_headers = {
        "X-Gateway-Secret":
            auth["backend_secret"],
        "X-Authenticated-Client":
            auth["client_id"]
    }
    
    content_type = request.headers.get(
        "content-type"
    )
    if content_type:
        gateway_headers[
            "content_type"
        ] = content_type
    try:
        async with httpx.AsyncClient(
            timeout=10.0
        ) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=gateway_headers
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Backend no disponible"
        )
    
    response_headers = {}
    if "content-type" in upstream.headers:
        response_headers[
            "content-type"
        ] = upstream.headers[
            "content-type"
        ]
        
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers
    )