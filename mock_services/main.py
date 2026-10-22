from fastapi import FastAPI, Query, status, Request, Response
from aggregator.schema import IncomingRequest
from typing import Annotated, Union
from aggregator.schema import ProviderResponse, ProviderResponseNegative, ProviderResponsePositive
import time
import aiohttp
import asyncio


app = FastAPI()


# /mock-provider-A?weight=20&scenario=normal
@app.get('/mock-provider-A', response_model=ProviderResponse)
async def provider_A(response: Response, filter_query: Annotated[IncomingRequest, Query()]):
    weight = filter_query.weight
    scenario = filter_query.scenario

    A = 500 + 100 * weight
    if scenario == 'normal' or scenario == 'retry' or scenario == 'partial':
        await asyncio.sleep(0.1)
        response = ProviderResponsePositive(provider_id='A', price_tenge=A, days=2)
        return response

    elif scenario == 'all_down':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ProviderResponseNegative(provider_id='A', detail=503)


@app.get('/mock-provider-B', response_model=ProviderResponse)
async def provider_B(request: Request, response: Response, filter_query: Annotated[IncomingRequest, Query()]):
    weight = filter_query.weight
    scenario = filter_query.scenario

    B = 400 + 120*weight
    if scenario == 'normal':
        await asyncio.sleep(0.1)
        response = ProviderResponsePositive(provider_id='B', price_tenge=B, days=3)
        return response

    elif scenario == 'partial':
        await asyncio.sleep(1.5)
        response = ProviderResponsePositive(provider_id='B', price_tenge=B, days=3)
        return response

    elif scenario == 'retry':
        if request.headers['x-attempt'] == '1':
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ProviderResponseNegative(provider_id='B', detail=503)

        response = ProviderResponsePositive(provider_id='B', price_tenge=B, days=3)
        return response

    elif scenario == 'all_down':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ProviderResponseNegative(provider_id='B', detail=503)


@app.get('/mock-provider-C')
async def provider_C(response: Response, filter_query: Annotated[IncomingRequest, Query()]):
    weight = filter_query.weight
    scenario = filter_query.scenario

    C = 700 + 80*weight
    if scenario == 'normal' or scenario == 'retry':
        await asyncio.sleep(0.1)
        response = ProviderResponsePositive(provider_id='C', price_tenge=C, days=1)
        return response

    elif scenario == 'partial':
        await asyncio.sleep(0.1)
        response = {
            'provider_id': 'C',
            'price_tenge': "error",
            'days': 1
        }
        return response

    elif scenario == 'all_down':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ProviderResponseNegative(provider_id='C', detail=503)