from flask import Flask
from flask import request
from flask import render_template, jsonify

import sqlite3

from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import json

from bs4 import BeautifulSoup

app = Flask(__name__)

def parse_nalog_ru(type, value):
    """
        Selenium вводит ИНН/ОГРН в форму и нажимает на кнопку.
        Далее парсится полученный html.
        После каждого действия небольшое ожидание загрузки страницы.
    """
    driver = webdriver.Chrome()
    driver.get('https://rmsp.nalog.ru/')
    try:
        field = driver.find_element_by_id('query')
        field.send_keys(value)
        time.sleep(1)
        act = driver.find_element_by_css_selector("button[class='btn-l btn-alert']")
        act.click()
        time.sleep(5)
        html_from_page = driver.page_source
        soup = BeautifulSoup(html_from_page)
        if type == 'ИНН':
            div = soup.find("div", {"class": "rsmp-result result-inn"})
            if div == None:
                return False
            else:
                return div.span.text == value
        else:
            div = soup.find("div", {"class": "rsmp-result result-ogrn"})
            if div == None:
                return False
            else:
                return div.span.text == value
    except Exception:
        return False
        
def save_result(cur, inn_or_ogrn, result):
    data = (inn_or_ogrn, 'Да' if result else 'Нет', datetime.now())
    cur.execute("INSERT INTO REQUESTS VALUES(?, ?, ?);", data)

@app.route('/', methods=['GET', 'POST'])
def hello_world():
    if request.method == 'POST':
        with sqlite3.connect('requests.db') as post_conn:
            post_cur = post_conn.cursor()
            
            inn_or_ogrn = request.form.to_dict()
            tp = json.loads(next(iter(inn_or_ogrn)))

#           Проверка на наличие недавнего запроса 
            try:
                post_cur.execute("""SELECT (julianday(datetime(CURRENT_TIMESTAMP, 'localtime')) - julianday(r.REQUEST_DTTM)) * 86400.0, r.RESULT
                                FROM REQUESTS r
                                JOIN (SELECT INN_OR_OGRN, MAX(REQUEST_DTTM) as mx
                                      FROM REQUESTS
                                      GROUP BY INN_OR_OGRN) m
                                      ON r.INN_OR_OGRN = m.INN_OR_OGRN AND r.REQUEST_DTTM = m.mx
                                WHERE r.INN_OR_OGRN = ?;""", [tp['value']])
                check_new = post_cur.fetchall()
                if len(check_new) > 0 and check_new[0][0] < 300:
                    render_string = ' найдены юрлица' if check_new[0][1] == 'Да' else ' юрлиц не найдено'
                    resp_dic={'msg':'По '+ tp['type']+ ' '+tp['value']+render_string}
                    resp = jsonify(resp_dic)
                    return resp
            except Exception:
                pass
                
#           Парсинг сайта                
            result = parse_nalog_ru(tp['type'], tp['value'])
            render_string = ' найдены юрлица' if result else ' юрлиц не найдено'
            resp_dic={'msg':'По '+ tp['type']+ ' '+tp['value']+render_string}
            resp = jsonify(resp_dic)
            save_result(post_cur, tp['value'], result)
            return resp
    else:
        with sqlite3.connect('requests.db') as get_conn:
            get_cur = get_conn.cursor()
            get_cur.execute("""SELECT INN_OR_OGRN, RESULT, REQUEST_DTTM 
                       FROM REQUESTS
                       ORDER BY REQUEST_DTTM DESC;""")
            data = get_cur.fetchall()
            return render_template('get.html', data=data)
        

if __name__ == '__main__':
    conn = sqlite3.connect('requests.db')
    cur = conn.cursor()
    cur.execute("DROP TABLE REQUESTS;")
    conn.commit()
    cur.execute("""CREATE TABLE IF NOT EXISTS REQUESTS(
                    INN_OR_OGRN TEXT,
                    RESULT TEXT,
                    REQUEST_DTTM timestamp);
                """)
    conn.commit()
    app.run(debug=True)