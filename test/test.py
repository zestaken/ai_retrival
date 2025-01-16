import os
import json
from langchain_openai import ChatOpenAI
import time

def compare_llm(text1, text2):
    start = time.time()
    """使用大模型对比两段话是否意思一致"""
    with open('../prompt.txt', 'r') as f:
        prompt_temp = f.read()
    prompt = prompt_temp.format(text1 = text1, text2 = text2)
    # 将openai的链接设置为fastchat部署的模型的api访问链接
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
    os.environ["OPENAI_API_BASE"] = "http://localhost:21002/v1"
    os.environ["OPENAI_API_KEY"] = "no need" # api key随便设置一个字符串，占位
    # 设置为本地的模型的名字
    model_name = "Qwen2.5-7B-Instruct"
    # json_llm = ChatOpenAI(model=model_name,
    #                       model_kwargs={ "response_format": {
    #                                     "same": "True_or_False",
    #                                     "explanation": "简要说明两段话是否表达相同意思的理由"}}) 
    json_llm = ChatOpenAI(model=model_name,
                          model_kwargs={ "response_format": {"same": "True_or_False"}}) 
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



text1 = "通过对计量全域数据的抽取、分析，结合可视化的仪表盘或表格等，实现数据的分析展现，直观的数据总览配合层层钻取追根溯源，可以帮助决策人员发现问题调整战略，甚至还可以以监控预警模式，实时刷新监控数据，可快速发现问题并及时响应。"
text2 = "本平台融合了先进的物联网技术和大数据处理能力，为用户提供全面的设备状态监测与故障预警服务。通过集成智能传感器收集的实时数据，结合专业的数据分析模型，平台能够提供详尽的设备健康报告和维护建议。此外，平台还支持自定义报警规则，一旦检测到异常情况，将立即通知相关人员，确保设备持续稳定运行。"
text3 = "本系统通过集成先进的大数据处理技术和机器学习算法，对业务运营数据进行深度挖掘和智能分析。结合丰富的图表和交互式仪表盘，提供全面的数据洞察和可视化展示。系统支持多维度的数据探索和深入分析，帮助管理层及时发现潜在问题并优化运营策略。同时，系统具备智能预警功能，能够自动识别异常数据并实时通知相关人员，确保问题得到迅速解决。"
res = compare_llm(text1, text2)
print(res)