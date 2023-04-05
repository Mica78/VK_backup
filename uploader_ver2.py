from datetime import datetime
import json
from time import sleep

import requests
from bs4 import BeautifulSoup


def logger(func):
    def wrapper(*args, **kwargs):
        print(f'Starting function: {str(func).split()[1]}')
        result = func(*args, **kwargs)
        if type(result) is str:
            print(str(func).split()[1], ': ', result)
        else:
            print(str(func).split()[1], ': ', f'data {result[0]} status: {result[1].status_code}')
        return result
    return wrapper


class Token:
    def __init__(self, flag='VK', token=None):
        self.flag = flag
        self.__token = token
        if self.token is None and self.flag == 'VK':
            self.get_vk_token()
        elif self.token is None and self.flag == 'YA':
            self.get_ya_token()

    @property
    def token(self):
        return self.__token

    @token.setter
    def token(self, token):
        self.__token = token

    def get_vk_token(self, file=".private/tokens.txt"):
        with open(file, encoding='utf-8') as file:
            self.token = file.readlines()[0].strip()

    def get_ya_token(self, file=".private/tokens.txt"):
        with open(file, encoding='utf-8') as file:
            self.token = file.readlines()[1].strip()


class VK:
    def __init__(self, token=None, vk_id=None, version='5.131'):
        self.auth = {"Authorization": f"Bearer {token}"}
        self.ver = {'v': version}
        self.data = []
        self.timeout = 5
        if vk_id.isdigit():
            self.id = vk_id
        else:
            self.id = self.get_id_from_link(vk_id)

    def get_id_from_link(self, link):
        response = requests.get(link)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            href = soup.find('a', attrs={'aria-label': "фотография"})
            return href.get('href').split("_")[0][6:]

    @logger
    def get_photos(self, number_of_photos=5, album_id='profile'):
        self.data.clear()
        url = "https://api.vk.com/method/photos.get"
        idx_offset = 0
        params = {
            'owner_id': f'{self.id}',
            'album_id': album_id,
            'extended': 1,
            'offset': idx_offset * 1000,
            'photo_sizes': 1,
            'feed_type': 'photo'
        }
        with requests.Session() as session:
            session.headers = self.auth
            session.params = {**self.ver, **params}
            while True:
                if number_of_photos > 1000:
                    count_param = {'count': 1000}
                    number_of_photos -= 1000
                else:
                    count_param = {'count': number_of_photos}
                try:
                    response = session.get(url, params=count_param, timeout=self.timeout)
                except requests.exceptions.Timeout:
                    return f'Loading timeout {self.timeout} sec'
                except ConnectionError:
                    return f'{datetime.now()}: Connection failed. Check connection'
                else:
                    if response.status_code != 200:
                        return response.status_code
                    if list(response.json().keys())[0] == 'error':
                        return response.json()['error']['error_msg']
                    if not response.json()['response']['items'] and self.data:
                        return f'End of data. Received {len(self.data)} foto/fotos'
                    if not response.json()['response']['items']:
                        return 'Response is empty'
                    for item in response.json()['response']['items']:
                        filename = str(item['likes']['count'])
                        for sizes in item['sizes']:
                            if sizes['type'] == 'w':
                                photo_url = sizes['url']
                                photo_size = sizes['type']
                                break
                            photo_url = sizes['url']
                            photo_size = sizes['type']
                        for data in self.data:
                            if filename in data.values():
                                filename = filename + '_' + str(item['date'])
                        self.data.append({'filename': filename, 'size': photo_size, 'url': photo_url})
                    if len(response.json()['response']['items']) <= number_of_photos or \
                            len(self.data) == number_of_photos:
                        return f'End of data. Received {len(self.data)} foto/fotos'
                    sleep(0.35)
                    idx_offset += 1


class YaDiskUploader:
    def __init__(self, token, data, vk_id, timeout=5):
        self.token = token
        self.data = data
        self.vk_id = vk_id
        self.auth = {'Authorization': f'OAuth {self.token}'}
        self.path_yadisk = f'/Загрузки/VKid_{self.vk_id}'
        self.url = 'https://cloud-api.yandex.net/v1/disk/resources/'
        self.timeout = timeout
        self.result = []

    @logger
    def create_folder(self, folder_name=str(datetime.today()).split()[0]):
        if not self.data:
            return 'No data from VK'
        self.path_yadisk = f'{self.path_yadisk}_{folder_name}/'
        try:
            response = requests.put(
                self.url,
                headers=self.auth,
                params={'path': self.path_yadisk}
            )
        except requests.exceptions.Timeout:
            return f'Loading timeout {self.timeout} sec'
        except ConnectionError:
            return f'{datetime.now()}: Connection failed. Check connection'
        else:
            if response.status_code == 201:
                return f'Directory {self.path_yadisk} created 201'
            elif response.status_code == 409:
                return f'Directory {self.path_yadisk} exists'
            else:
                return str(response.json()["description"])

    @logger
    def get_response(self, data, session, url, headers, params):
        for i in range(5):
            try:
                response = session.get(url, headers=headers, params=params, timeout=self.timeout)
            except requests.exceptions.Timeout:
                return f'{data}: timeout {self.timeout} sec'
            except Exception:
                sleep(20)
                continue
            else:
                if response.status_code != 200:
                    return response.json()['message']
                return data, response

    @logger
    def send_photo_to_ya_disk(self):
        self.result.clear()
        href_url = f'{self.url}upload'
        with requests.Session() as sess:
            with requests.Session() as sess2:
                for data in self.data:
                    res_photo_url = self.get_response(data['url'], sess2, data['url'], headers=None, params=None)
                    file_ext = res_photo_url[1].headers['Content-Type'].split('/')[1]
                    filename = data['filename'] + '.' + file_ext

                    params = {
                        'path': self.path_yadisk + filename,
                        'overwrite': 'true'
                    }

                    if int(res_photo_url[1].headers['Content-Length']) != len(res_photo_url[1].content):
                        continue
                    res_href = self.get_response(
                        data=filename,
                        session=sess,
                        url=href_url,
                        headers=self.auth,
                        params=params
                    )
                    if isinstance(res_href[1], str) or res_href[1].status_code != 200 or \
                            res_photo_url[1].status_code != 200:
                        continue
                    else:
                        for i in range(3):
                            try:
                                res_to_upload = sess.put(res_href[1].json()["href"], data=res_photo_url[1].content)
                            except Exception:
                                sleep(20)
                                continue
                            else:
                                if res_to_upload.status_code == 201 or res_to_upload.status_code == 202:
                                    self.result.append({'file': filename, 'size': data['size']})
                                else:
                                    return f'Error YaDisk {res_to_upload.status_code}'
                                break
                    sleep(0.35)
                return f'Uploaded {len(self.result)} files.\nEnd of upload.'

    def write_result_json(self, file=None):
        if not file:
            with open(f'{self.vk_id}.json', "w") as file:
                json.dump(self.result, file, indent=4)
        else:
            with open(file, "w") as file:
                json.dump(self.result, file, indent=4)


def main(vk_id, number_of_photo, album):
    vk_token = Token(flag='VK')
    vk = VK(token=vk_token.token, vk_id=vk_id)
    vk.get_photos(number_of_photos=number_of_photo, album_id=album)
    ya_token = Token(flag='YA')
    ya_disk = YaDiskUploader(ya_token.token, vk.data, vk_id=vk.id)
    ya_disk.create_folder()
    ya_disk.send_photo_to_ya_disk()
    ya_disk.write_result_json()


if __name__ == '__main__':
    usr_id = '16685737'
    usr_id = 'https://vk.com/netology'
    album = 'wall'
    # album = 'profile'
    main(usr_id, number_of_photo=5, album=album)
