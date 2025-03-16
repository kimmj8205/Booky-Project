import requests
import sys
import json
import os
from flask import request
from flask import Flask, jsonify
from xml.etree import ElementTree
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from google.cloud import language_v1
import random
from urllib.parse import quote
from bs4 import BeautifulSoup
application = Flask(__name__)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gckey.json"

# @application.route("/")
# def hello():
#     return "Hello goorm!"

#알라딘 검색 
def search_aladin(book_name):
    try:
        encoded_book_name = quote(book_name)
        search_url = f"https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=All&SearchWord={encoded_book_name}&x=0&y=0"
        search_response = requests.get(search_url)
        search_soup = BeautifulSoup(search_response.text, 'html.parser')
        first_book_tag = search_soup.select_one('.ss_book_list ul li a.bo3')
        if first_book_tag is None:
            return None
        first_book_url = first_book_tag['href']
        response = requests.get(first_book_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        isbn_tag = soup.find('meta', {'property': 'books:isbn'})
        if isbn_tag:
            return isbn_tag['content']
    except Exception as e:
        print(f"An error occurred: {e}")
    return None

#yes24 검색 
def search_yes24(book_name):
    try:
        encoded_book_name = quote(book_name)
        search_url = f"https://www.yes24.com/Product/Search?domain=ALL&query={encoded_book_name}"
        search_response = requests.get(search_url)
        search_soup = BeautifulSoup(search_response.text, 'html.parser')
        first_book_tag = search_soup.select_one('#yesSchList li a.lnk_img')
        if first_book_tag is None:
            return None
        first_book_url = "https://www.yes24.com" + first_book_tag['href']
        response = requests.get(first_book_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        isbn_tag = soup.find('meta', {'property': 'books:isbn'})
        if isbn_tag:
            return isbn_tag['content']
    except Exception as e:
        print(f"An error occurred: {e}")
    return None

#전체 검색 함수 
def search_book_isbn(book_name):
    # 먼저 알라딘에서 ISBN을 검색합니다.
    isbn_aladin = search_aladin(book_name)
    
    # 알라딘에서 ISBN을 찾지 못한 경우, YES24에서 검색을 시도합니다.
    if isbn_aladin is None:
        isbn_yes24 = search_yes24(book_name)
        if isbn_yes24 is not None:
            return isbn_yes24  # YES24에서 찾은 ISBN을 반환
        else:
            return "검색 결과가 없습니다."  # 두 서점 모두에서 찾지 못한 경우
    else:
        return isbn_aladin  # 알라딘에서 찾은 ISBN을 반환




@application.route('/rising', methods=['POST']) #대출 급상승 도서
def rising():
    #인증키 값 : 
    
    # 현재 날짜와 시간을 가져옴
    now = datetime.now()

    # 하루 전 날짜 계산
    one_day_before = now - timedelta(days=1)

    # 날짜를 yyyy-mm-dd 형식으로 포맷팅
    formatted_date = one_day_before.strftime("%Y-%m-%d")
    
    api_url = "https://data4library.kr/api/hotTrend?authKey=인증키값&searchDt="+ formatted_date

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)

    carousel_items = []
    # 각 result 요소에 대해 처리
    for result in root.findall(".//result"):

        date = result.find('date').text if result.find('date') is not None else 'No date'
        # 각 result 요소 내의 doc 요소들에 대해 처리
        for doc in result.findall(".//doc"):
            no = doc.find('no').text if doc.find('no') is not None else 'No number'

            # bookname 처리
            bookname_element = doc.find('bookname')
            bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'

            #대출 순위 상승폭은 넣자 difference
            difference = doc.find('difference').text if doc.find('difference') is not None else 'No data'
            
            # bookImageURL 처리
            book_image_url_element = doc.find('bookImageURL')
            book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''


            #대출 순위 상승폭 추가
            carousel_items.append({
                "title": f"대출 급상승 도서 {date} - {no}위: {bookname}",
                "description": f"전주 대비 순위 상승폭: {difference}",
                "thumbnail": {
                    "imageUrl": book_image_url
                }
            })

    res = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "carousel": {
                        "type": "basicCard",
                        "items": carousel_items
                    }
                }
            ]
        }
    }

    return jsonify(res)


def get_isbn_readKing(): #파라미터 받아오는 함수
    json_data = request.get_json()
    blank = json_data['action']['params']['isbn_code_readKing']
    return blank

@application.route('/readKing', methods=['POST']) #다독자 추천 도서
def readKing():


    api_url = "http://data4library.kr/api/recommandList?authKey=인증키값&type=reader&isbn13="+search_book_isbn(get_isbn_readKing())

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)

    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for book in root.findall('.//book'):
        no = book.find('no').text if book.find('no') is not None else 'No number'

        # bookname 처리
        bookname_element = book.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'

        # bookImageURL 처리
        book_image_url_element = book.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # 케로셀 아이템 생성
        carousel_items.append({
            "title": f"다독자 추천 도서 {no}: {bookname}",
            "description": "",
            "thumbnail": {
                "imageUrl": book_image_url
            },
        })

    if(len(carousel_items)==0):
        res = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "검색 결과가 없습니다."}}]
            }
        }
    else:
        res = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "carousel": {
                            "type": "basicCard",
                            "items": carousel_items
                        }
                    }
                ]
            }
        }

    return jsonify(res)


def get_isbn_mania(): #파라미터 받아오는 함수
    json_data = request.get_json()
    return json_data['action']['params']['isbn_code_mania']

@application.route('/mania', methods=['POST']) #마니아 추천 도서
def mania():

    api_url = "http://data4library.kr/api/recommandList?authKey=인증키값&type=mania&isbn13="+search_book_isbn(get_isbn_mania())

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)

    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for book in root.findall('.//book'):
        no = book.find('no').text if book.find('no') is not None else 'No number'

        # bookname 처리
        bookname_element = book.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'

        # bookImageURL 처리
        book_image_url_element = book.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # 케로셀 아이템 생성
        carousel_items.append({
            "title": f"마니아 추천도서 {no}: {bookname}",
            "description": "",
            "thumbnail": {
                "imageUrl": book_image_url
            },
        })
        
    if(len(carousel_items)==0):
        res = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "검색 결과가 없습니다."}}]
            }
        }
    else:
        res = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "carousel": {
                            "type": "basicCard",
                            "items": carousel_items
                        }
                    }
                ]
            }
        }

    return jsonify(res)


def get_byAge(): #파라미터 받아오는 함수
    json_data = request.get_json()
    return json_data['action']['params']['age']

@application.route('/byAge', methods=['POST']) #연령별 추천 도서
def byAge():
    
    # 현재 날짜와 시간을 가져옴
    now = datetime.now()

    # 한달 전 날짜 계산
    one_month_before = now - relativedelta(months=1)

    # 날짜를 yyyy-mm-dd 형식으로 포맷팅
    formatted_month = one_month_before.strftime("%Y-%m-%d")

    #나이대 입력 받은 값으로 전환되도록 수정
    api_url = "http://data4library.kr/api/loanItemSrch?authKey=인증키값&startDt="+formatted_month+"+&age="+get_byAge()[0:2]+"&pageNo=1&pageSize=10"

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)

    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for doc in root.findall('.//doc'):
        no = doc.find('no').text if doc.find('no') is not None else 'No number'

        # bookname 처리
        bookname_element = doc.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'

        loan_count = doc.find('loan_count').text if doc.find('loan_count') is not None else 'No data'
        ranking = doc.find('ranking').text if doc.find('ranking') is not None else 'No data'

        # bookImageURL 처리
        book_image_url_element = doc.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # bookDtlUrl 처리
        bookDtlUrl_element = doc.find('bookDtlUrl')
        bookDtlUrl = bookDtlUrl_element.text.strip() if bookDtlUrl_element is not None and bookDtlUrl_element.text is not None else ''

        # 케로셀 아이템 생성
        carousel_items.append({
            "title": f"연령별 인기 도서 {ranking}위 : {bookname}",
            "description": f"대출 횟수: {loan_count}",
            "thumbnail": {
                "imageUrl": book_image_url,
                "link": {
                    "web": bookDtlUrl
                }
            },
        })

    res = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "carousel": {
                        "type": "basicCard",
                        "items": carousel_items
                    }
                }
            ]
        }
    }

    return jsonify(res)


paramList = ['isbn13', 'srchkeyword', 'srchtitle', 'srchauthor', 'srchage', 'srchregion', 'srchkdc', 'srchdtl_kdc']

def get_param():
    return_value = ""
    json_data = request.get_json()
    if 'isbn13' in json_data['action']['params']:
        json_data['action']['params']['isbn13'] = search_book_isbn(json_data['action']['params']['isbn13'].replace(" ", ""))
    for param in paramList:
        if param in json_data['action']['params']:
            return_value += (f"&{param}=" if param == 'isbn13' else f"&{param[4:]}=") + json_data['action']['params'][param].replace(" ", "")
    return return_value


@application.route('/srchBooks', methods=['POST']) #키워드 기반 도서 검색
def srchBooks():
    api_url = "http://data4library.kr/api/srchBooks?authKey=인증키값"+get_param()

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)
    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for doc in root.findall('.//doc'):

        # bookname 처리
        bookname_element = doc.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'
        # authors  처리
        authors_element = doc.find('authors')
        authors = authors_element.text.strip() if authors_element is not None and authors_element.text is not None else 'No authurs'

        # bookImageURL 처리
        book_image_url_element = doc.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # bookDtlUrl 처리
        bookDtlUrl_element = doc.find('bookDtlUrl')
        bookDtlUrl = bookDtlUrl_element.text.strip() if bookDtlUrl_element is not None and bookDtlUrl_element.text is not None else ''

 
        # 케로셀 아이템 생성
        carousel_items.append({
            "title": bookname,
            "description": f"저자:{authors}",
            "thumbnail": {
                "imageUrl": book_image_url,
                "link": {
                    "web": bookDtlUrl
                }
            },
        })
        
    if(len(carousel_items)==0):
        res = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "아직 알고리즘에 등록되지 않은 코드입니다."}}]
            }
        }
    else:
        res = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "carousel": {
                            "type": "basicCard",
                            "items": carousel_items
                        }
                    }
                ]
            }
        }

    return jsonify(res)


@application.route('/loanItemSrch', methods=['POST']) #인기대출도서 조회
def loanItemSrch():
    api_url = "http://data4library.kr/api/loanItemSrch?authKey=인증키값"+get_param()

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)
    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for doc in root.findall('.//doc'):

        # bookname 처리
        bookname_element = doc.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'
        # authors  처리
        authors_element = doc.find('authors')
        authors = authors_element.text.strip() if authors_element is not None and authors_element.text is not None else 'No authurs'

        # bookImageURL 처리
        book_image_url_element = doc.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # bookDtlUrl 처리
        bookDtlUrl_element = doc.find('bookDtlUrl')
        bookDtlUrl = bookDtlUrl_element.text.strip() if bookDtlUrl_element is not None and bookDtlUrl_element.text is not None else ''

        # 케로셀 아이템 생성
        carousel_items.append({
            "title": bookname,
            "description": f"저자:{authors}",
            "thumbnail": {
                "imageUrl": book_image_url,
                "link": {
                    "web": bookDtlUrl
                }
            },
        })
    if(len(carousel_items)==0):
        res = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "아직 알고리즘에 등록되지 않은 코드입니다."}}]
            }
        }
    else:
        res = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "carousel": {
                            "type": "basicCard",
                            "items": carousel_items
                        }
                    }
                ]
            }
        }

    return jsonify(res)

@application.route('/lib', methods=['POST'])
def library():
    data = request.get_json()
    #print(data)
    try:
        user_location = data['action']['detailParams']['sys_location']['value']
        #print(user_location)
    except KeyError:
        user_location = 'default'

    REST_API_KEY = '69f70258cdc846437fa9bb4a3dcceef1'
    headers = {
        "Authorization": f"KakaoAK {REST_API_KEY}"
    }
    
    geo_params = {
        "query": user_location
    }
    geo_response = requests.get("https://dapi.kakao.com/v2/local/search/address.json", headers=headers, params=geo_params)
    
    if geo_response.status_code == 200:
        geo_data = geo_response.json().get('documents', [])
        if geo_data:
            lon = geo_data[0]['x']  # 경도
            lat = geo_data[0]['y']  # 위도
        else:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "주소 검색 결과 없음"}}]
                }
            })
    else:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "주소 검색 API 요청 실패"}}]
            }
        })
    
    # query 파라미터 설정: 사용자 위치 + " 도서관"
    params = {
        "query": f"{user_location} 도서관",
        "x": lon,  # 경도
        "y": lat,  # 위도
        "sort": "distance"  # 거리순 정렬
    }

    response = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params=params)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }

        })
    #지도 파트
    search_results = response.json().get('documents', [])
    
    #이거는 리스트형식일때만 사용
    list_items = search_results[:5]
    
    kakao_map_search_url = f"http://map.kakao.com/?q={user_location} 도서관"
    
    list_cards_items = [
        {
            "title": lib['place_name'],
            "description": f"전화번호: {lib['phone']} | 주소: {lib['road_address_name']}",
            "link": {
                "web": lib['place_url']
            }
        }
        for lib in list_items
    ]

    res = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "listCard": {
                        "header": {
                            "title": f"{user_location} 지역의 도서관 검색 결과"
                        },
                        "items": list_cards_items,
                        "buttons": [
                            {
                                "label": "더보기",
                                "action": "webLink",
                                "webLinkUrl": kakao_map_search_url
                            }
                        ]
                    }
                }
            ]
        }
    }

    return jsonify(res)

def get_feeling_recommandBooks(): #파라미터 받아오는 함수
    json_data = request.get_json()
    return json_data['action']['params']['feeling_content2']

emotion_keywords = {
"매우 긍정적": ["기쁨", "행복", "환희", "즐거움", "흥분", "감사", "만족감", "황홀", "열광", "뿌듯", "자부심", "경이로움", "환호", "기대감", "희열"],
"긍정적": ["만족", "희망", "안심", "평온", "감동", "고마움", "자신감", "용기", "설렘", "편안", "흡족", "안도감", "기대", "긍지", "용기"],
"중립적": ["평범", "무관심", "담담함", "무덤덤", "시큰둥", "덤덤", "무감동", "무반응", "무심", "평이", "무표정", "무감정", "무신경", "무감각"],
"부정적": ["실망", "불만족", "좌절", "후회", "걱정", "우울", "스트레스", "불안", "짜증", "염려", "갈등", "회의", "비관", "무기력", "답답"],
"매우 부정적": ["슬픔", "분노", "공포", "절망", "비통", "좌절감", "절규", "격분", "증오", "두려움", "경악", "공포심", "질투", "원한", "탄식"]
}

def analyze_sentiment(text_content):
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(content=text_content, type_=language_v1.Document.Type.PLAIN_TEXT)
    response = client.analyze_sentiment(document=document)
    sentiment = response.document_sentiment
    return sentiment.score

def get_emotion_keyword(score):
    if score >= 0.8:
        emotion_level = "매우 긍정적"
    elif score >= 0.5:
        emotion_level = "긍정적"
    elif score > -0.3:
        emotion_level = "중립적"
    elif score > -0.8:
        emotion_level = "부정적"
    else:
        emotion_level = "매우 부정적"
    
    keywords = emotion_keywords[emotion_level]
    return random.choice(keywords)

@application.route('/recommand', methods=['POST'])
def recommandBooks():
    sentiment_score = analyze_sentiment(get_feeling_recommandBooks())
    sentiment_keyword = get_emotion_keyword(sentiment_score)

    print(sentiment_keyword)

    api_url = "http://data4library.kr/api/srchBooks?authKey=인증키값&keyword=" + sentiment_keyword

    response = requests.get(api_url)

    if response.status_code != 200:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "API 요청 실패"}}]
            }
        })

    xml_data = response.text
    root = ElementTree.fromstring(xml_data)
    carousel_items = []

    # 각 <book> 요소에 대해 처리
    for doc in root.findall('.//doc'):

        # bookname 처리
        bookname_element = doc.find('bookname')
        bookname = bookname_element.text.strip() if bookname_element is not None and bookname_element.text is not None else 'No book name'
        # authors  처리
        authors_element = doc.find('authors')
        authors = authors_element.text.strip() if authors_element is not None and authors_element.text is not None else 'No authurs'

        # bookImageURL 처리
        book_image_url_element = doc.find('bookImageURL')
        book_image_url = book_image_url_element.text.strip() if book_image_url_element is not None and book_image_url_element.text is not None else ''

        # bookDtlUrl 처리
        bookDtlUrl_element = doc.find('bookDtlUrl')
        bookDtlUrl = bookDtlUrl_element.text.strip() if bookDtlUrl_element is not None and bookDtlUrl_element.text is not None else ''

        # 케로셀 아이템 생성
        carousel_items.append({
            "title": bookname,
            "description": f"저자:{authors}",
            "thumbnail": {
                "imageUrl": book_image_url,
                "link": {
                    "web": bookDtlUrl
                }
            },
        })
        
    if(len(carousel_items)==0):
        res = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "검색 결과가 없습니다."}}]
            }
        }
    else:
        res = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "carousel": {
                            "type": "basicCard",
                            "items": carousel_items
                        }
                    }
                ]
            }
        }

    return jsonify(res)


#새로운 스킬 생성하려면 @application.route('/주소', methods=['POST']) 새롭게 선언

#서버를 작동 시키려면 콘솔창에 python3 application.py 명령어 입력, 중지는 Ctrl+C
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)
