# Сервис для агрегации нескольких запросов по доставке товаров  
Учебный FastAPI-сервис, агрегирующий запросы с трех mock-сервисов (offers, failures) с валидацией, ограничением ожидания и асинхронностью.  

## Запуск  
`docker-compose up --build`

## Контракты  
Контракт входящего запроса:  
```
class IncomingRequest(BaseModel):
    weight: int = Field(ge=1, le=20)
    scenario: Literal['normal', 'partial', 'retry', 'all_down']
```  
Контракт положительного и отрицательного ответа от mock-сервиса:
```
class ProviderResponsePositive(BaseModel):
    model_config = ConfigDict(strict=True)

    response_type: Literal['positive'] = Field(default="positive", exclude=True)
    provider_id: str
    price_tenge: int = Field(ge=1)
    days: int = Field(ge=1, le=30)


class ProviderResponseNegative(BaseModel):
    model_config = ConfigDict(strict=True)

    response_type: Literal['negative'] = Field(default="negative", exclude=True)
    provider_id: str
    detail: Any
```
JSON возвращаемого ответа от главного сервиса:
```
response: 200 / 502
offers: {
	provider_id: str
	price_tenge: positive int
	days: int 1 - 30
},
failures: {
	provider_id: str
	reason: str (timeout, unavailable, invalid_response)
	attempts: int
}
```

## Ручной протокол (запрос -> журнал -> ответ)
1. Первый сценарий  
   **Запрос:** http://127.0.0.1:8000/quotes?weight=2&scenario=normal  
   **Журнал:**  
   <img width="1526" height="77" alt="image" src="https://github.com/user-attachments/assets/158272df-3faa-4f31-ab25-260840a34f98" />
   **Ответ:**  
   <img width="292" height="457" alt="image" src="https://github.com/user-attachments/assets/ee28c713-1293-4d1e-82e5-b036e0d29a76" />
2. Второй сценарий  
   **Запрос:** http://127.0.0.1:8000/quotes?weight=2&scenario=partial  
   **Журнал:**  
   <img width="1255" height="118" alt="image" src="https://github.com/user-attachments/assets/1e63cdf4-db95-4e4d-904c-43676d178069" />  
   **Ответ:**  
   <img width="325" height="437" alt="image" src="https://github.com/user-attachments/assets/7ea26d9d-27ee-4ada-aa86-f06e69c6b88c" />  
3. Третий сценарий  
   **Запрос:** http://127.0.0.1:8000/quotes?weight=2&scenario=retry  
   **Журнал:**  
    <img width="1208" height="113" alt="image" src="https://github.com/user-attachments/assets/fca725a5-0fab-4756-9ec6-9bb740f154ce" />  
    **Ответ:**  
    <img width="266" height="471" alt="image" src="https://github.com/user-attachments/assets/a424b03f-5cc3-4822-a281-3fc6c03f09d9" />  
4. Четвертый сценарий
   **Запрос:** http://127.0.0.1:8000/quotes?weight=2&scenario=all_down  
   **Журнал:**  
    <img width="1208" height="170" alt="image" src="https://github.com/user-attachments/assets/c5d0013e-d59b-4035-b43a-7d6f82452d6a" />  
    **Ответ:**  
    <img width="282" height="402" alt="image" src="https://github.com/user-attachments/assets/192255b5-7bf2-4512-be00-a2e8c5e948cf" />  
## Конкурентность и остановка  
Конкурентность видна в журнале, остановка производится за счет этой функции:
```
finally:
  cancel_queue = []
  for task in tasks:
      if not task.done():
          cancel_queue.append(task)
  await cancel_tasks(cancel_queue)

async def cancel_tasks(tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    return ''
```
    
