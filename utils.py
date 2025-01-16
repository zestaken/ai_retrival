import os
import pymysql
import json
import os
import xiangshi as xs
import faiss
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
import time
from datetime import datetime
import logging
import subprocess
# 进行参数校验需要的包
from flask_wtf import FlaskForm
from wtforms import StringField,IntegerField
from wtforms.validators import ValidationError
import wtforms.validators as validators
from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma

def load_llm(file_path='./log/llm_pids.txt'):
    """加载大模型"""
    controller_command = "/root/anaconda3/envs/ai/bin/python3 -m fastchat.serve.controller --host 0.0.0.0 --port 21001 >./log/controller.log 2>&1 "
    worker_command = "/root/anaconda3/envs/ai/bin/python3 -m fastchat.serve.model_worker --controller http://localhost:21001 --model-path  /root/code/models/Qwen2.5-7B-Instruct --num-gpus 1 >./log/model_worker.log --port 12346 --worker http://localhost:12346  2>&1 "
    api_command = "/root/anaconda3/envs/ai/bin/python3 -m fastchat.serve.openai_api_server --host 0.0.0.0 --port 21002 --controller http://localhost:21001 >./log/api.log 2>&1 "
    try:
        proc1 = subprocess.Popen(controller_command, shell=True)
        proc2 = subprocess.Popen(worker_command, shell=True)
        proc3 = subprocess.Popen(api_command, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"LLM model load failed with error code {e.returncode}")
        print(e.output.decode("utf-8"))
    procs = [proc1, proc3, proc2]   
    with open(file_path, 'w') as f:
        for proc in procs:
            pid = proc.pid
            f.write(str(pid)+"\n")
    return procs

def stop_llm(file_path='./log/llm_pids.txt'):
    """关闭fastchat大模型进程"""
    try:
        with open(file_path, 'r') as f:
            pids_str = f.read()
            if "-1" == pids_str: # 没有pid，不进行kill
                return 
            pids = pids_str.split('\n')

            for pid in pids:
                pid = pid.strip()  # 去除空格
                if pid:
                    subprocess.run(['kill', '-9', pid], check=True)
                    print(f"已成功关闭PID为 {pid} 的进程")
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查文件路径是否正确。")
    except subprocess.CalledProcessError as e:
        print(f"无法关闭PID为 {pid} 的进程，错误信息：{e}")
    finally:
        with open(file_path,'w') as f:
            f.write("-1")

def is_directory_empty(directory_path):
    """检查指定目录是否为空。

    Args:
        directory_path (str): 目录路径。

    Returns:
        bool: 如果目录为空返回True，否则返回False。
    """
    # 检查目录是否存在
    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        raise FileNotFoundError(f"The directory '{directory_path}' does not exist.")

    # 遍历目录内容
    for _, dirs, files in os.walk(directory_path):
        # 如果存在任何文件或子目录，则认为目录不为空
        if files or dirs:
            return False

    # 如果没有找到任何文件或子目录，则认为目录为空
    return True

def save_doc_ids(ids, save_folder):
    """保存ids列表为json文件"""
    name = 'doc_ids.json'
    file_name = os.path.join(save_folder, name)
    # 将列表保存到JSON文件中
    with open(file_name, 'w') as file:
        json.dump(ids, file)

    print(f"ids saved to {file_name}")

def read_doc_ids(save_folder):
    """从json文件中读取ids列表"""
    name = 'doc_ids.json'
    file_name = os.path.join(save_folder, name)
    # 从JSON文件读取列表
    with open(file_name, 'r') as file:
        ids = json.load(file)

    return ids

def create_vector_store(vector_store_path, embedding_model):
    """创建Vector store和对应的Document id列表"""
    if is_directory_empty(vector_store_path):
        # 如果vector store未曾创建则创建，如果创建了则直接读取
        d = 1024 # embedding向量的维度               
        index = faiss.IndexFlatL2(d)
        Vector_store = FAISS(
            embedding_function=embedding_model,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )
        #创建后保存
        Vector_store.save_local(vector_store_path, "langching_vector_store")
        Document_ids =[]
        save_doc_ids(Document_ids, vector_store_path)
    else:
        #直接读取vector store
        Vector_store = FAISS.load_local(vector_store_path, embedding_model, "langching_vector_store",allow_dangerous_deserialization=True)
        Document_ids = read_doc_ids(vector_store_path)
    
    return Vector_store, Document_ids

def connect_database():
    """连接数据库"""
    host_name="10.151.1.64"
    port = 3306
    user_name="dbuser"
    user_password = "Chachong@123"
    db_name = "ai_check"
    connection = None
    try:
        connection = pymysql.connect(
            host=host_name,
            user=user_name,
            port = port,
            passwd=user_password,
            database=db_name,
            charset='utf8'
        )
        print("Connection to MySQL DB successful")
    except Exception as e:
        print(f"The error '{e}' occurred")

    return connection

def compare_words(text1, text2):
    """jaccard算法比较两句话词相似度"""
    score_jacc = xs.jaccard(text1, text2)
    
    return score_jacc

def compare_llm(text1, text2):
    start = time.time()
    """使用大模型对比两段话是否意思一致"""
    with open('./prompt.txt', 'r') as f:
        prompt_temp = f.read()
    prompt = prompt_temp.format(text1 = text1, text2 = text2)
    # 将openai的链接设置为fastchat部署的模型的api访问链接
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
    os.environ["OPENAI_API_BASE"] = "http://localhost:21002/v1"
    os.environ["OPENAI_API_KEY"] = "no need" # api key随便设置一个字符串，占位
    # 设置为本地的模型的名字
    model_name = "Qwen2.5-7B-Instruct"
    json_llm = ChatOpenAI(model=model_name,
                          model_kwargs={ "response_format": {
                                        "same": "True_or_False",
                                        "explanation": "简要说明两段话是否表达相同意思的理由"}}) 
    # json_llm = ChatOpenAI(model=model_name,
                        #   model_kwargs={ "response_format": {"same": "True_or_False"}}) 
    #3. 设置模型的json模式
    answer = json_llm.invoke(prompt)
    print(answer.content)
    end = time.time()

    try:
        res_json = json.loads(answer.content)
        res = res_json['same']
        if res == 'True':
            score = 1
        elif res == 'False':
            score = 0
        else: # 输出内容不能识别，返回-1，不使用大模型判断的结果
            print(res)
            score = -1
    except Exception as e:
        print(f"大模型输出故障：{e}")
        return -1
    print(end - start)
    return score

def compute_score(score_llm, score_jaac, score_vector):
    """计算最终相似度"""
    if score_llm < 0:
        score_all = score_jaac * 0.3 + score_vector * 0.7
    else:
        score_all = score_jaac * 0.3 + score_llm*0.4 + score_vector * 0.3
    if score_jaac == 1:
        #如果词相似度完全一致，则直接判定为100%相似
        score_all = 1
    score_all = round(score_all, 3) #只保留三位小数
    
    return score_all
        
    

def getLogger():
    # 获取当前时间戳
    current_timestamp = time.time()
    # 将时间戳转换为 datetime 对象
    dt_object = datetime.fromtimestamp(current_timestamp)
    # 使用 strftime 将 datetime 对象格式化为字符串
    formatted_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
    # 利用服务器启动时间戳生成当前的日志记录文件名，每次启动服务器的日志文件不同
    # log_file_path = f'/root/ai_server/log/server_{formatted_time}.log'
    log_file_path = f'./log/server.log'
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_file_path)
    formatter = logging.Formatter('%(asctime)s - %(levelname)-2s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# def set_sim_text():
#     """为文本设置同义文本"""
# 参数校验相关
class CustomIntListValidator:
    def __call__(self, form, field):
        try:
            if field.data == "":
                field.int_list = ""
            else:
                # 尝试将输入字符串转换为整数列表
                int_list = [int(item.strip()) for item in field.data.split(',')]
                field.int_list = int_list
        except Exception:
            # 如果转换失败，抛出验证错误
            raise ValidationError('Invalid parameters,Examples of correct parameters:{"projectIds":"1,2,3,4"}')
        
class IdtagForm(FlaskForm):
    """校验参数是否为列表和整数(add接口专用)"""
    #校验projectId是否为整数(是一个整数值或者字符串整数均可)
    projectId = StringField("projectId",[validators.InputRequired()]) 
    tag = IntegerField("tag", [validators.InputRequired()]) # 校验tag是否为整数(是一个整数值或者字符串整数均可)
    
    class Meta:
        csrf = False  # 再次确认关闭 CSRF

class IdsForm(FlaskForm):
    """校验参数是否为列表(delete接口专用)"""
    ids = StringField("ids", validators=[CustomIntListValidator()]) #校验ids是否为整数字符串
    
    class Meta:
        csrf = False  # 再次确认关闭 CSRF

class IdtagIdsForm(FlaskForm):
    """校验参数是否为列表和整数(match接口专用)"""
    projectId = StringField("projectId",[validators.InputRequired()])
    tag = IntegerField("tag", [validators.InputRequired()]) # 校验tag是否为整数(是一个整数值或者字符串整数均可)
    #校验projectIds是否为整数字符串或者空字符串
    projectIds = StringField("projectIds", validators=[CustomIntListValidator()]) 
    
    class Meta:
        csrf = False  # 再次确认关闭 CSRF

def create_chroma(vector_store_path, embedding_model):
    """创建Vector store和对应的Document id列表"""
    Vector_store = Chroma(
            collection_name = "test_collection",
            embedding_function=embedding_model,
            persist_directory=vector_store_path
        )
    path = vector_store_path + "/doc_ids.json"
    if not os.path.exists(path):
        # 如果vector store未曾创建则创建，如果创建了则直接读取          

        #创建后保存
        # Vector_store.save_local(vector_store_path, "langching_vector_store")
        Document_ids =[]
        save_doc_ids(Document_ids, vector_store_path)
    else:
        #直接读取vector store
        # Vector_store = FAISS.load_local(vector_store_path, embedding_model, "langching_vector_store",allow_dangerous_deserialization=True)
        Document_ids = read_doc_ids(vector_store_path)
    
    return Vector_store, Document_ids