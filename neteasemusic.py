from bs4 import BeautifulSoup
import requests
import json
from tqdm import tqdm
import sqlite3
import os
from datetime import datetime
import matplotlib. dates as mdates
import matplotlib. pyplot as plt
from matplotlib.pyplot import figure
import matplotlib.ticker as ticker
import re

class Alarm:
    OK = '\033[92m' #GREEN
    WARNING = '\033[93m' #YELLOW
    FAIL = '\033[91m' #RED
    RESET = '\033[0m' #RESET COLOR
    
    def success(msg: str) -> None:
        print(Alarm.OK + "[SUCC] " + Alarm.RESET + msg)
    
    def warning(msg: str) -> None:
        print(Alarm.WARNING + "[WARN] " + Alarm.RESET + msg)

    def fail(msg: str) -> None:
        print(Alarm.FAIL + "[FAIL] " + Alarm.RESET + msg)
    
    def info(msg: str) -> None:
        print("[INFO] " + msg)

class AnalyzerBase:
    con = None
    cur = None

    def __init__(self):
        self.headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, sdch',
                'Accept-Language': 'zh-CN,zh;q=0.8,en;q=0.6',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Cookie': '',
                'DNT': '1',
                'Host': 'music.163.com',
                'Pragma': 'no-cache',
                'Referer': 'http://music.163.com/',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36'
            }

        self.session = requests.session()
        self.session.headers.update(self.headers)
    
    def __del__(self):
        if self.con is not None:
            self.con.close()

class AlbumAgeAnalyzer(AnalyzerBase):
    def choose_user_and_playlist(self):
        # 获取用户id
        userid_list = self.cur.execute('''SELECT pids, uid FROM web_user_playlist''').fetchall()
        cnt = 1
        print("id, name")
        for data in userid_list:
            addr = 'https://music.163.com/user/home?id=%s' % data[1]
            response = requests.get(addr, headers=self.headers)
            soup = BeautifulSoup(response.content.decode(), 'html.parser')
            print("%d, %s" % (cnt, json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['title']))
            cnt += 1
        print('------------select your id------------')
        sel = int(input())
        # 找到该用户所有的pid (playlist id)
        playlist_list = [item for item in userid_list[sel-1][0].strip().split(',') if item != '']
        # 获取歌单id
        cnt = 1
        print("id, name")
        for data in playlist_list:
            try:
                addr = 'https://music.163.com/playlist?id=%s' % data
                response = requests.get(addr, headers=self.headers)
                soup = BeautifulSoup(response.content.decode(), 'html.parser')
                print("%d, %s" % (cnt, json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['title']))
                cnt += 1
            except:
                print("%d, %s" % (cnt, "PRIVATE LIST"))
                cnt += 1
        print('------------select your id------------')
        sel = int(input())
        self.playlistid = playlist_list[sel-1]
    
    def crawl_playlist(self):
        # 获取歌单歌曲
        album_list = self.cur.execute('''SELECT a.tid, b.track FROM web_playlist_track a
        LEFT JOIN web_track b
        ON a.tid = b.tid
        WHERE a.pid = '%s' ''' % (self.playlistid)).fetchall()

        failed_list = []
        # 生成歌曲所属专辑时间的文件
        # 根据专辑id请求网页，获得专辑时间
        with open('result.txt', 'w', encoding='utf-8') as target:
            for _, data in tqdm(album_list):
                if data is None:
                    Alarm.warning("Your playlist seems not complete, please open playlist in your NetEase Music App and wait for loading.")
                else:
                    albuminfo = json.loads(data)
                    try:
                        addr = 'https://music.163.com/album?id=' + str(albuminfo['album']['id'])
                        song = albuminfo['name']
                        response = requests.get(addr, headers=self.headers)
                        if response.status_code != 200:
                            failed_list.append((albuminfo, "request failed"))
                        else:
                            soup = BeautifulSoup(response.content.decode('utf-8', 'ignore'), 'html.parser')
                            try:
                                date = json.loads(soup.find('script', {'type': 'application/ld+json'}).string)['pubDate']
                                target.writelines(song + ',' + date + '\n')
                            except Exception as e:
                                failed_list.append((albuminfo, "content error"))
                    except TypeError:
                        failed_list.append((albuminfo, "type error"))

        Alarm.info('%d songs failed' % len(failed_list))
        for item in failed_list:
            print(item)
    
    def gen_age_graph(self):
        if os.path.exists('result.txt') == False:
            Alarm.fail('result.txt not found')
            return
        # 绘制散点图
        dates = []
        with open('result.txt', 'r', encoding='utf-8') as f:
            for line in f:
                dates.append(re.search('\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', line).group())

        ys = [datetime.strptime(m,'%Y-%m-%dT%H:%M:%S' ).date() for m in dates]
        ys.reverse()
        xs = list(range(len(ys)))
        # setting
        width = 8
        height = 6
        figure(figsize=(width, height), dpi=100)
        plt.gca().yaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().yaxis.set_major_locator(mdates.DayLocator())
        # plot
        plt.scatter(xs, ys, s=4)
        plt.xticks([])
        plt.yticks([])
        plt.gca().yaxis.set_major_locator(ticker.MultipleLocator(((max(ys)-min(ys))/height/2).days))
        plt.gca().xaxis.set_major_locator(ticker.MultipleLocator(len(xs)/width/2))
        plt.savefig('result.png', bbox_inches='tight')
        plt.show()
    

class WindowsAlbumAgeAnalyzer(AlbumAgeAnalyzer):
    '''
    解析网易云音乐windows版的数据库
    '''
    def __init__(self):
        super().__init__()
        self.con = sqlite3.connect('%s/Netease/CloudMusic/Library/webdb.dat' % os.environ['localappdata'])
        self.cur = self.con.cursor()

if __name__ == "__main__":
    try:
        Analyzer = WindowsAlbumAgeAnalyzer()
        Analyzer.choose_user_and_playlist()
        Analyzer.crawl_playlist()
        Analyzer.gen_age_graph()
    except Exception as e:
        Alarm.fail(e)
        os._exit(-1)