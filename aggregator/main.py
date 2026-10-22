from fastapi import FastAPI, Query, status, Response, Request
from typing import Annotated
import time
import aiohttp
from aiohttp import ClientError, ClientConnectionError
import asyncio
import logging
import os
from operator import itemgetter
from .schema import IncomingRequest, ProviderResponsePositive, ProviderResponseNegative
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, filename='aggregator.log', filemode='w',
                    format='%(levelname)s %(message)s')
# logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')  # Для докера


@asynccontextmanager
async def create_clientsession(app: FastAPI):
    async with aiohttp.ClientSession() as session:
        yield {'http_session': session}

app = FastAPI(lifespan=create_clientsession)
PROVIDER_BASE_URL = os.getenv("PROVIDER_BASE_URL", "http://127.0.0.1:8001").rstrip('/')
request_id = 0
count = 0

async def getRequestId():
    global request_id
    request_id += 1
    return request_id


async def logger(start_time, request_id,  provider_id,  attempt, result):
    end_time = time.perf_counter()
    duration = round(end_time - start_time, 2)
    logging.info(f'request_id: {request_id}, provider_id: {provider_id}, attempt: {attempt}, '
                 f'time span: {round(start_time, 2)} -> {round(end_time, 2)}, duration: {duration}, result: {result}')
    return ''


async def sort_values(offers):
    # аналогично key=lambda x: (x['price_tenge'], x['days'], x['provider_id'])
    new_offers = sorted(offers, key=itemgetter("price_tenge", "days", "provider_id"))
    return new_offers


async def proceed_pending_tasks(pendings, provider_dict, attempts_dict, result):
    for pending in pendings:
        provider_id = provider_dict[pending]
        result.append([{'provider_id': provider_id, 'reason': 'timeout', 'attempts': attempts_dict[provider_id]}, 'failures'])

    return ''


async def cancel_tasks(tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return ''


async def aggregator_response(res):
    response_dict = {'offers': [], 'failures': []}

    for elem in res:
        if elem[1] == 'offers':
            response_dict['offers'].append(elem[0])
        if elem[1] == 'failures':
            response_dict['failures'].append(elem[0])

    if response_dict['offers']:
        response_dict['offers'] = await sort_values(response_dict['offers'])  # посмотреть что лучше sort или sorted
    return response_dict


async def fetch_mock_service(session, semaphore, request_id, url, params, provider_id, attempts_dict):
    reason = None

    for attempt in range(1, 3):
        service_response = None

        async with semaphore:
            start = time.perf_counter()
            attempts_dict[provider_id] = attempt

            try:
                async with session.get(url, params=params, headers={'X-Attempt': str(attempt)}, timeout=0.8) as response:
                    raw_json = await response.text()

                    if response.status == 503:
                        reason = 'unavailable'
                        await logger(start, request_id, provider_id, attempt, reason)

                    elif response.status == 200:

                        try:
                            service_response = ProviderResponsePositive.model_validate_json(raw_json)
                        except Exception:
                            await logger(start, request_id,  provider_id,  attempt, result='invalid_response')
                            return [{'provider_id': provider_id, 'reason': 'invalid_response', 'attempts': attempt}, 'failures']

                        if service_response.provider_id != provider_id:
                            await logger(start, request_id,  provider_id,  attempt, result='invalid_response')
                            return [{'provider_id': provider_id, 'reason': 'invalid_response', 'attempts': attempt}, 'failures']

                        await logger(start, request_id,  provider_id,  attempt, service_response)
                        return [{'provider_id': provider_id, 'price_tenge': service_response.price_tenge, 'days': service_response.days, 'attempts': attempt}, 'offers']

                    else:
                        await logger(start, request_id,  provider_id,  attempt, result='invalid_response')
                        return [{'provider_id': provider_id, 'reason': 'invalid_response', 'attempts': attempt}, 'failures']

            except TimeoutError:
                reason = 'timeout'
                await logger(start, request_id, provider_id, attempt, reason)

            except ClientConnectionError:
                await logger(start, request_id, provider_id, attempt, result='unavailable')
                return [{'provider_id': provider_id, 'reason': 'unavailable', 'attempts': attempt}, 'failures']

            except ClientError:
                await logger(start, request_id,  provider_id,  attempt, result='invalid_response')
                return [{'provider_id': provider_id, 'reason': 'invalid_response', 'attempts': attempt}, 'failures']

            except asyncio.CancelledError:
                await logger(start, request_id,  provider_id,  attempt, result='timeout')
                raise

        if attempt == 1:
            await asyncio.sleep(0.1)

    return [{'provider_id': provider_id, 'reason': reason, 'attempts': 2}, 'failures']


async def request_mock_service(session, weight, scenario):
    params = {'weight': weight, 'scenario': scenario}
    semaphore = asyncio.Semaphore(2)
    request_id = await getRequestId()

    attempts_dict = {
        'A': 0,
        'B': 0,
        'C': 0
    }
    provider_dict = {
        asyncio.create_task(fetch_mock_service(session, semaphore, request_id, f"{PROVIDER_BASE_URL}/mock-provider-A",
            params, provider_id='A', attempts_dict=attempts_dict)): 'A',
        asyncio.create_task(fetch_mock_service(session, semaphore, request_id, f'{PROVIDER_BASE_URL}/mock-provider-B',
            params, provider_id='B', attempts_dict=attempts_dict)): 'B',
        asyncio.create_task(fetch_mock_service(session, semaphore, request_id, f'{PROVIDER_BASE_URL}/mock-provider-C',
            params, provider_id='C', attempts_dict=attempts_dict)): 'C',
    }

    tasks = list(provider_dict.keys())
    result = []

    try:
        done, pending = await asyncio.wait(tasks, timeout=4)
        for future in done:
            result.append(future.result())
        if pending:
            await proceed_pending_tasks(pending, provider_dict, attempts_dict, result)

    finally:
        cancel_queue = []
        for task in tasks:
            if not task.done():
                cancel_queue.append(task)
        await cancel_tasks(cancel_queue)

    return result

# quotes?weight=20&scenario=normal
@app.get('/quotes')
async def getRequest(request: Request, response: Response, filter_query: Annotated[IncomingRequest, Query()]):
    session = request.state.http_session

    res = await request_mock_service(session, filter_query.weight, filter_query.scenario)

    make_response = await aggregator_response(res)
    if not make_response['offers']:
        response.status_code = status.HTTP_502_BAD_GATEWAY
        return make_response
    return make_response
