from datetime import datetime
import json
from time import sleep

import requests


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


class VK:
    def __init__(self, token_vk=None, vk_id=None, version='5.131'):
        if token_vk:
            self.__token = token_vk
        else:
            self.get_vk_token_from_file()
        self.vk_id = vk_id
        self.auth_vk = {"Authorization": f"Bearer {self.__token}"}
        self.ver = {'v': version}
        self.data = []
        self.timeout = 5

    @property
    def token_vk(self):
        return self.__token

    @token_vk.setter
    def token_vk(self, token_vk):
        self.__token = token_vk
        self.auth_vk = {"Authorization": f"Bearer {self.__token}"}

    def get_vk_token_from_file(self, file=".private/tokens.txt"):
        with open(file, encoding='utf-8') as file:
            self.__token = file.readlines()[0].strip()
            self.auth_vk = {"Authorization": f"Bearer {self.__token}"}

    @logger
    def get_photos(self, number_of_photos=5, album_id='profile'):
        self.data.clear()
        url = "https://api.vk.com/method/photos.get"
        idx_offset = 0
        params = {
                'owner_id': f'{self.vk_id}',
                'album_id': album_id,
                'extended': 1,
                'offset': idx_offset * 1000,
                'photo_sizes': 1,
                'feed_type': 'photo'
                }
        with requests.Session() as session:
            session.headers = self.auth_vk
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
                        for sizes in item['sizes']:
                            if sizes['type'] == 'w':
                                photo_url = sizes['url']
                                photo_size = sizes['type']
                                break
                            photo_url = sizes['url']
                            photo_size = sizes['type']
                        self.data.append({'likes': item['likes']['count'], 'date': item['date'], 'size': photo_size, 'url': photo_url})
                    if len(self.data) == number_of_photos:
                        return f'End of data. Received {len(self.data)} foto/fotos'
                    sleep(0.35)
                    idx_offset += 1


class VkToYandexDisk(VK):
    def __init__(self, yatoken=None, **kwargs):
        super().__init__(**kwargs)
        if yatoken:
            self.__yatoken = yatoken
        else:
            self.get_ya_token_from_file()
        self.auth_ya = {'Authorization': f'OAuth {self.__yatoken}'}
        self.path_yadisk = {
                            'url': f'/Загрузки/VKid{self.vk_id}',
                            }

    def get_ya_token_from_file(self, file=".private/tokens.txt"):
        with open(file, encoding='utf-8') as file:
            self.__yatoken = file.readlines()[1].strip()
            self.auth_ya = {'Authorization': f'OAuth {self.__yatoken}'}

    @property
    def yatoken(self):
        return self.__yatoken

    @yatoken.setter
    def yatoken(self, token):
        self.__yatoken = token
        self.auth_ya = {'Authorization': f'OAuth {self.__yatoken}'}

    @logger
    def create_folder(self, folder_name=str(datetime.today()).split()[0]):
        url = f'https://cloud-api.yandex.net/v1/disk/resources/'
        self.path_yadisk['url'] = f'/Загрузки/VKid{self.vk_id}_{folder_name}/'
        try:
            response = requests.put(url, headers=self.auth_ya, params={'path': self.path_yadisk['url']})
        except requests.exceptions.Timeout:
                return f'Loading timeout {self.timeout} sec'
        except ConnectionError:
                return f'{datetime.now()}: Connection failed. Check connection'
        else:
            if response.status_code == 201:
                return 'Directory ' + self.path_yadisk['url'] + f' created 201'
            elif response.status_code == 409:
                return 'Directory ' + self.path_yadisk['url'] + ' exists'
            else:
                return response.status_code

    @logger
    def get_response(self, data, session, url, headers, params):
        counter = 0
        while counter <= 5:
            try:
                response = session.get(url, headers=headers, params=params, timeout=self.timeout)
            except requests.exceptions.Timeout:
                    return f'{data}: timeout {self.timeout} sec'
            except ConnectionError:
                sleep(3000)
                continue
            else:
                return data, response

    @logger
    def send_photo_to_ya_disk(self):
        self.result = []
        filenames = []
        if not self.data:
            return 'No data from VK'
        href_url = f'https://cloud-api.yandex.net/v1/disk/resources/upload'
        with requests.Session() as sess:
            with requests.Session() as sess2:
                for data in self.data:
                    res_photo_url = self.get_response(data['url'], sess2, data['url'], headers=None, params=None)
                    file_ext = res_photo_url[1].headers['Content-Type'].split('/')[1]
                    filename = str(data['likes']) + '.' + file_ext
                    if filename in filenames:
                        filename = str(data['likes']) + '_' + str(data['date']) + '.' + file_ext
                    filenames.append(filename)

                    params = {
                            'path': self.path_yadisk['url'] + filename,
                            'overwrite': 'true'
                        }

                    if int(res_photo_url[1].headers['Content-Length']) != len(res_photo_url[1].content):
                        continue
                    res_href = self.get_response(data=filename, session=sess, url= href_url, headers=self.auth_ya, params=params)
                    if res_href[1].status_code != 200 or res_photo_url[1].status_code != 200:
                        continue
                    else:
                        try:
                            res_to_upload = sess.put(res_href[1].json()["href"], data=res_photo_url[1].content)
                        except ConnectionError:
                            sleep(1800)
                            try:
                                res_to_upload = sess.put(res_href[1].json()["href"], data=res_photo_url[1].content)
                            except ConnectionError:
                                continue
                            else:
                                self.result.append({'file': filename, 'size': data['size']})
                        else:
                            self.result.append({'file': filename, 'size': data['size']})
                    sleep(0.35)
                return f'Uploaded {len(self.result)} files.\nEnd of upload.'

    def write_result_json(self, file=None):
        if not file:
            with open (f'{self.vk_id}.json', "w") as file:
                json.dump(self.result, file, indent=4)
        else:
            with open (file, "w") as file:
                json.dump(self.result, file, indent=4)


def main(user_id):
    vy = VkToYandexDisk(vk_id=user_id)
    if vy.get_photos() == 'This profile is private':
        exit()
    vy.create_folder()
    vy.send_photo_to_ya_disk()
    vy.write_result_json()


if __name__ == '__main__':
    user_id = '16685737'
    main(user_id)
