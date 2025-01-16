import requests

url_addText = 'http://127.0.0.1:2222/addText'
url_deleteText ='http://127.0.0.1:2222/deleteText'
url_matchText = 'http://127.0.0.1:2222/matchText'
url_matchTextFast = 'http://127.0.0.1:2222/matchTextFast'
#功能点的接口
url_addFunction = 'http://127.0.0.1:2222/addFunction'
url_deleteFunction ='http://127.0.0.1:2222/deleteFunction'
url_matchFunction = 'http://127.0.0.1:2222/matchFunction'
url_matchFunctionFast = 'http://127.0.0.1:2222/matchFunctionFast'

ids = []
for i in range(1, 20):
    ids.append(i)
ids = [str(id)for id in ids]
ids = ",".join(ids)
addText_data = {'tag':29 ,'projectId': 21}
# # 1.添加文档
# r_addtext= requests.post(url=url_addText,json=addText_data) # 较慢
# print(r_addtext.text)
# # 1.添加功能点
addFunction_data = {'tag':35 ,'projectId': 2}
r_addFunction= requests.post(url=url_addFunction,json=addFunction_data)
print(r_addFunction.text)

# # # # # # 2. 删除文档
# deleteText_data = {"ids": ids}
# r_deleteText = requests.post(url = url_deleteText, json=deleteText_data)
# print(r_deleteText.text)
# # # # # # 2. 删除功能点
# deleteFunction_data = {"ids": "1,3"}
# r_deleteFunction = requests.post(url = url_deleteFunction, json=deleteFunction_data)
# print(r_deleteFunction.text)

# # # # # 3. 文本查重
# match_text = {'tag':1, 'projectId': 1, 'projectIds': "1,53"}
# r_matchText = requests.post(url = url_matchText, json = match_text)
# print(r_matchText.text)
# # # # # 3. 快速文本查重
match_text_fast = {'tag':30, 'projectId': 21, 'projectIds': "-1"}
r_matchText_fast = requests.post(url = url_matchTextFast, json = match_text_fast)
print(r_matchText_fast.text)
# # # # 3.功能点查重
# match_Function = {'tag':1, 'projectId': 1, 'projectIds': "-1"}
# r_matchFunction = requests.post(url = url_matchFunction, json = match_Function)
# print(r_matchFunction.text)
# # # # 3.快速功能点查重
# match_Function_Fast = {'tag':1, 'projectId': 1, 'projectIds': "-1"}
# r_matchFunction_fast = requests.post(url = url_matchFunctionFast, json = match_Function)
# print(r_matchFunction_fast.text)

