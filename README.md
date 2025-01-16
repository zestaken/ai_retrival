# 查重算法接口说明文档

程序运行的地址：
```
ip: 127.0.0.1
port:55555
```
其中所提到的`id`均指文本在数据库的`id`值。
## 1.添加文本到文本向量库的接口
* 请求方法：Post
* 请求url：http://127.0.0.1:55555/addText
* 请求体：json数据。输入要添加到向量库中文本的数据库中的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2, 3, 4,5"}`
* 返回的内容：`{"status": "200", 'tag': 1, "repeat ids": [1,3], "time-consuming": 5.897s}`。其中`repeat ids`指出文本向量库已经存在而导致本次没有存入的id。没有重复的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 2.添加功能点文本到功能点向量库的接口
* 请求方法：Post
* 请求url：http://127.0.0.1:55555/addFunction
* 请求体：json数据。输入要添加到向量库中功能点文本的数据库中的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2, 3, 4,5"}`
* 返回的内容：`{"status": "200", 'tag': 1, "repeat ids": [1,3], "time-consuming": 5.897s}`。其中repeat ids指出功能点向量库已经存在而本次没有存入的id。没有重复的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 3.删除文本向量库中指定文本向量的接口
* 请求方法：Post
* 请求url：http://127.0.0.1:55555/deleteText
* 请求体：json数据。输入需要从文本向量库中删除的id列表字符串，json的键名为`ids`。例如：`{'ids': "1, 3"}`
* 返回的内容：`{"status": "200", "delete ids": [1,3], "time-consuming": 5.897s}}`。其中delete ids指出成功删除的id列表。没有成功的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 4.删除功能点向量库指定功能点文本向量的接口
* 请求方法：Post
* 请求url：http://127.0.0.1:55555/deleteFunction
* 请求体：json数据。输入需要从功能点向量库中删除的id列表字符串，json的键名为`ids`。例如：`{'ids': "1, 3"}`
* 返回的内容：`{"status": "200", "delete ids": [1,3], "time-consuming": 5.897s}}`。其中delete ids指出成功删除的id列表。没有成功的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 5.从文本向量库检索相似文本的接口

* 请求方法：Post
* 请求url：http://127.0.0.1:55555/matchText
* 请求体：json数据。输入需要从文本向量库中进行查重的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2"}`
* 返回的内容：`{"status": "200", "tag":1, "match text result": "(7, 8, 0.726),(9, 8, 0.776)", "time-consuming": 5.897s}}`。其中`match text result`是查重的结果，每一个结果是一个**三元组**：第一项是待查重文本的id，第二项是查重到的文本的id，第三项是相似度。当有多个查重结果时，每个查重结果的三元组之间用`,`分隔没有成功的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 6.从功能点向量库检索相似功能点的接口

* 请求方法：Post
* 请求url：http://127.0.0.1:55555/matchFunction
* 请求体：json数据。输入需要从功能点向量库中进行查重的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2"}`
* 返回的内容：`{"status": "200", "tag": 1,"match function result": "(7, 8, 0.726),(9, 8, 0.776)", "time-consuming": 5.897s}}`。其中`match function result`是查重的结果，每一个结果是一个**三元组**：第一项是待查重功能点的id，第二项是查重到的功能点的id，第三项是相似度。当有多个查重结果时，每个查重结果的三元组之间用`,`分隔。没有查重的结果时，值为空字符串。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 7.从文本向量库快速检索相似文本的接口

* 请求方法：Post
* 请求url：http://127.0.0.1:55555/matchTextFast
* 请求体：json数据。输入需要从文本向量库中进行查重的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2"}`
* 返回的内容：`{"status": "200", "tag":1, "match text result": "(7, 8, 0.726),(9, 8, 0.776)", "time-consuming": 5.897s}}`。其中`match text result`是查重的结果，每一个结果是一个**三元组**：第一项是待查重文本的id，第二项是查重到的文本的id，第三项是相似度。当有多个查重结果时，每个查重结果的三元组之间用`,`分隔没有成功的id时，值为`null`。
* 成功的状态码：`200`
* 失败的状态码：`500`

## 8.从功能点向量库快速检索相似功能点的接口

* 请求方法：Post
* 请求url：http://127.0.0.1:55555/matchFunctionFast
* 请求体：json数据。输入需要从功能点向量库中进行查重的id列表字符串和其所属的文档类型tag，json的键名为`ids`和`tag`。例如：`{'tag':1, ids': "1, 2"}`
* 返回的内容：`{"status": "200", "tag": 1,"match function result": "(7, 8, 0.726),(9, 8, 0.776)", "time-consuming": 5.897s}}`。其中`match function result`是查重的结果，每一个结果是一个**三元组**：第一项是待查重功能点的id，第二项是查重到的功能点的id，第三项是相似度。当有多个查重结果时，每个查重结果的三元组之间用`,`分隔。没有查重的结果时，值为空字符串。
* 成功的状态码：`200`
* 失败的状态码：`500`