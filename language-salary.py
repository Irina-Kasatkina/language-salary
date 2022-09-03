import logging
import os
import time

from dotenv import load_dotenv
import requests
from terminaltables import AsciiTable


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(filename='language-salary.log', filemode='w')


HH_MOSCOW_AREA = 1
PERIOD_IN_DAYS = 30
SJ_MOSCOW_ID = 4
SJ_IT_SECTION = 33


def download_vacancies_hh(language):
    """
    Скачивает с hh.ru вакансии программистов на указанном языке
    программирования в Москве за 30 дней и возвращает список вакансий.
    """

    url = 'https://api.hh.ru/vacancies/'
    headers = {'User-Agent': 'HH-User-Agent'}
    params = {
        'area': HH_MOSCOW_AREA,
        'period': PERIOD_IN_DAYS,
        'search_field': 'name'
    }
    search_text = 'Программист'
    if language:
        search_text = f'{search_text} {language}'
    params['text'] = search_text

    page = 0
    number_of_pages = 1

    vacancies = []
    while page < number_of_pages:
        params['page'] = page
        while True:
            try:
                logger.info(f'Запрос "{search_text}" c {url} - страница {page}')
                page_response = requests.get(url, headers=headers, params=params)
                page_response.raise_for_status()
                page_json = page_response.json()
                vacancies.extend(page_json['items'])
                number_of_pages = page_json['pages']
            except requests.HTTPError:
                logger.warning(
                    f'При загрузке страницы {page} запроса "{search_text}" '
                    f'c {url} возникла ошибка HTTPError.'
                )
            except requests.exceptions.ConnectionError:
                logger.warning(
                    f'При загрузке страницы {page} запроса "{search_text}" '
                    f'c {url} возникла ошибка соединения с сайтом.'
                )
                time.sleep(30)
                continue
            break
        page += 1
    return vacancies


def download_vacancies_sj(language, secret_key):
    """
    Скачивает с superjob.ru вакансии программистов на указанном языке
    программирования в Москве и возвращает список вакансий.
    """

    url = 'https://api.superjob.ru/2.0/vacancies/'
    headers = {'X-Api-App-Id': secret_key}
    params = {
        'catalogues': SJ_IT_SECTION,
        'no_agreement': 1,
        'town': SJ_MOSCOW_ID
    }
    if language:
        params['keyword'] = language

    page = 0
    more_pages = True

    vacancies = []
    while more_pages:
        params['page'] = page
        while True:
            try:
                logger.info(f'Запрос "Программист {language}" c {url} - страница {page}')
                page_response = requests.get(url, headers=headers, params=params)
                page_response.raise_for_status()
                page_json = page_response.json()
                vacancies.extend(page_json['objects'])
                more_pages = page_json['more']
            except requests.HTTPError:
                logger.warning(
                    f'При загрузке страницы {page} запроса "Программист {language}" '
                    f'c {url} возникла ошибка HTTPError.'
                )
            except requests.exceptions.ConnectionError:
                logger.warning(
                    f'При загрузке страницы {page} запроса "Программист {language}" '
                    f'c {url} возникла ошибка соединения с сайтом.'
                )
                time.sleep(30)
                continue
            break
        page += 1
    return vacancies


def get_statistics(language, vacancies, predict_salaries):
    predict_salaries = [x for x in predict_salaries if x]
    vacancies_found = len(vacancies)
    vacancies_processed = len(predict_salaries)
    average_salary = sum(predict_salaries) // len(predict_salaries)
    return [language, vacancies_found, vacancies_processed, average_salary]


def predict_rub_salary_hh(vacancy):
    """
    Подсчитывает предполагаемую зарплату в рублях по вакансии,
    полученной с сайта hh.ru.
    """

    if (
            not vacancy or
            not vacancy['salary'] or
            vacancy['salary']['currency'] != 'RUR'
       ):
        return None
    return predict_salary(vacancy['salary']['from'], vacancy['salary']['to'])


def predict_rub_salary_sj(vacancy):
    """
    Подсчитывает предполагаемую зарплату в рублях по вакансии,
    полученной с сайта superjob.ru.
    """

    if not vacancy or (vacancy['currency'] != 'rub'):
        return None
    return predict_salary(vacancy['payment_from'], vacancy['payment_to'])


def predict_salary(salary_from, salary_to):
    """
    Подсчитывает предполагаемую зарплату в рублях
    по заданной вилке зарплат.
    """

    counters = {
        (True, True): lambda x, y: (x + y) // 2,
        (True, False): lambda x, y: int(x * 1.2),
        (False, True): lambda x, y: int(y * 0.8),
        (False, False): lambda x, y: None
    }
    counter = counters[(bool(salary_from), bool(salary_to))]
    return counter(salary_from, salary_to)


def main():
    load_dotenv()
    sj_secret_key = os.environ['SJ_SECRET_KEY']

    languages = ['Python', 'C++', 'C#', 'Go', 'Java', 'JavaScript', 'PHP', 'Ruby']
    table_cap = ('Язык', 'Вакансий найдено', 'Вакансий обработано', 'Средняя зарплата')

    statistics_hh = [table_cap]
    for language in languages:
        vacancies_hh = download_vacancies_hh(language=language)
        predict_salaries_hh = [predict_rub_salary_hh(x) for x in vacancies_hh]
        statistics_hh.append(get_statistics(language, vacancies_hh, predict_salaries_hh))

    table_instance_hh = AsciiTable(statistics_hh, title='HeadHunter Moscow')
    print(table_instance_hh.table)
    print()

    statistics_sj = [table_cap]
    for language in languages:
        vacancies_sj = download_vacancies_sj(language=language, secret_key=sj_secret_key)
        predict_salaries_sj = [predict_rub_salary_sj(x) for x in vacancies_sj]
        statistics_sj.append(get_statistics(language, vacancies_sj, predict_salaries_sj))

    table_instance_sj = AsciiTable(statistics_sj, 'SuperJob Moscow')
    print(table_instance_sj.table)
    print()


if __name__ == '__main__':
    main()
