from flask import Flask, request,jsonify
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_core.documents import Document
import utils
import time
import signal
from apscheduler.schedulers.background import BackgroundScheduler
import time
from langchain_chroma import Chroma

# def long_running_task():
#     # 模拟长时间运行的任务
#     time.sleep(10)
#     print("任务完成")

# scheduler = BackgroundScheduler()
# scheduler.add_job(func=set_sim_text, trigger="interval", minutes=30)
# scheduler.start()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test'
# app.config['WTF_CSRF_ENABLED'] = False  # 显式关闭 CSRF

# def set_sim_text():
    

# 服务器启动时加载大模型
# utils.load_llm()
# 向量库的构建,embedding模型的加载要在服务器启动之前
Vector_store_path = "./data/vector_store"
Vector_store_func_path = "./data/vector_store_func"
model_name = "../models/BGE"
model_kwargs = {"device": "cuda:0"}
encode_kwargs = {"normalize_embeddings": True}                                                                                                                                                
embedding_model = HuggingFaceBgeEmbeddings(
    model_name=model_name, model_kwargs=model_kwargs, encode_kwargs=encode_kwargs
) #开头大写的变量，代表全局变量，是后面会使用而在开始初始化的变量
Vector_store, Document_ids = utils.create_chroma(Vector_store_path, embedding_model)
Vector_store_func, Document_ids_func = utils.create_chroma(Vector_store_func_path, embedding_model)

# 日志记录
Logger = utils.getLogger()

# 接口1
@app.route("/addText", methods=['POST'])
def add_text():
    """往向量数据库中添加文本"""
    Logger.info("接受到addText请求：")
    start_time = time.time()
    form = utils.IdtagForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":500, "error":str(form.errors)}), 500
    else:
        projectId = int(form.projectId.data)
        tag = int(form.tag.data)
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"添加的项目id列表：{projectId}")
        # 根据id，从向量数据库中读取数据
        try:
            connection = utils.connect_database()
            cursor = connection.cursor()
            # query = f"""
            #         SELECT
            #             dr.id AS documentId,
            #             dsr.id AS sentenceId,
            #             dsr.sentence_content
            #         FROM
            #             ai_document_record dr
            #             INNER JOIN ai_document_paragraph_record dpr ON dpr.document_id = dr.id
            #             INNER JOIN ai_document_sentence_record dsr ON dsr.paragraph_id = dpr.id
            #         WHERE
            #             dr.project_id = {projectId}
            #             AND dr.tag = {tag};
            #         """
            query = f"""
                SELECT
                dr.id AS documentId,
                dsr.id AS sentenceId,
                dsr.sentence_content,
                dr.version AS version
            FROM
                ai_document_record dr
                INNER JOIN (
                    SELECT project_id, tag, MAX(version) as max_version
                    FROM ai_document_record
                    WHERE project_id = {projectId} AND tag = {tag}
                    GROUP BY project_id, tag
                ) subq ON dr.project_id = subq.project_id AND dr.tag = subq.tag AND dr.version = subq.max_version
                INNER JOIN ai_document_paragraph_record dpr ON dpr.document_id = dr.id
                INNER JOIN ai_document_sentence_record dsr ON dsr.paragraph_id = dpr.id
            WHERE
                dr.project_id = {projectId}
                AND dr.tag = {tag};
            """
            # sql = "SELECT `id`, `sentence_content`,`paragraph_id` FROM `ai_document_sentence_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            cursor.execute(query)
            results = cursor.fetchall()
            Logger.info("数据库读取数据成功")
        except Exception as e:
            Logger.info("数据库读取数据失败")
            return jsonify({"status":500, "error":str(e)}), 500
        finally:
            #不管是否成功运行，都要关闭数据库连接
            Logger.info("关闭数据库连接")
            connection.close()
        # 根据从数据库中读取的数据构建document
        documents = []
        document_ids = [] #本次添加的id列表
        repeat_ids = []
        for result in results:
            id = result[1]
            text = result[2]
            if text == None:
                continue
            if id in Document_ids:
                #如果该文件已经保存过，则不保存到向量库中
                repeat_ids.append(id)
                continue
            doc_id = result[0]
            version = result[3]
            # Logger.info(f"version: {version}")
            document = Document(
                page_content = text,
                metadata={'id': id, 'tag':tag, 'projectID':projectId, 'doc_id':doc_id},
                id = id
            )
            documents.append(document)
            document_ids.append(id) 
            Document_ids.append(id) # 向全局id列表中添加   
        # 添加的documents不能为空
        if len(documents) > 0:
            document_ids = [str(num) for num in document_ids]
            Vector_store.add_documents(documents=documents, ids=document_ids)
            #保存修改后的doc id到本地,chroma的vector store是自动保存的
            utils.save_doc_ids(Document_ids,Vector_store_path)
            Logger.info("修改后的向量库与id列表保存成功")
            # 将存入向量库的文本在数据库中的状态修改为0
            try:
                connection = utils.connect_database()
                cursor = connection.cursor()
                sql = "UPDATE ai_document_sentence_record SET status = 0 WHERE id IN ({})".format(', '.join(['%s'] * len(document_ids)))
                Logger.info(f"sql: {sql}")
                cursor.execute(sql, tuple(document_ids))
                connection.commit()
                Logger.info("数据库status修改成功")
            except Exception as e:
                Logger.info("数据库status修改失败")
                return jsonify({"status":500, "error":str(e)}), 500
            finally:
                Logger.info("关闭数据库连接")
                connection.close()
        if len(repeat_ids) > 0:
            # 将数字列表转换为字符串列表
            str_numbers = [str(num) for num in repeat_ids]
            str_repeat_ids = ",".join(str_numbers)
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("addText请求完成")
            return jsonify({"status": 200, "tag": tag, "projectID":projectId,"repeat ids": str_repeat_ids, "total texts": len(document_ids),"time-consuming": total_time}), 200
        else:
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("addText请求完成")
            return jsonify({"status": 200, "tag": tag, "projectID":projectId,"repeat ids": None,  "total texts": len(document_ids),"time-consuming": total_time}), 200
    
# 接口2
@app.route("/addFunction", methods=['POST'])
def add_func():
    """往向量数据库中添加功能"""
    start_time = time.time()
    Logger.info("接受到addFunction请求：")
    form = utils.IdtagForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":500, "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        projectId = form.projectId.data
        tag = form.tag.data
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"添加的项目id：{projectId}")
        try:
            connection = utils.connect_database()
            # 根据id，从向量数据库中读取数据
            cursor = connection.cursor()
            query = f"""
                SELECT
                    dr.id AS documentId,
                    dsr.id AS sentenceId,
                    dsr.function_point_description
                FROM
                    ai_document_record dr
                    INNER JOIN (
                    SELECT project_id, tag, MAX(version) as max_version
                    FROM ai_document_record
                    WHERE project_id = {projectId} AND tag = {tag}
                    GROUP BY project_id, tag
                ) subq ON dr.project_id = subq.project_id AND dr.tag = subq.tag AND dr.version = subq.max_version
                    INNER JOIN ai_function_record dsr ON dsr.document_id = dr.id
                WHERE
                    dr.project_id = {projectId}
                    AND dr.tag = {tag};
                """
            # sql = "SELECT `id`, `function_point_description`,`document_id` FROM `ai_function_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            # cursor.execute(sql,tuple(ids))
            cursor.execute(query)
            results = cursor.fetchall()
            Logger.info("数据库读取数据成功")
        except Exception as e:
            Logger.info("数据库读取数据失败")
            return jsonify({"status":500, "error":str(e)}), 500
        finally:
            Logger.info("关闭数据库连接")
            connection.close()
        # 根据从数据库中读取的数据构建document
        documents = []
        document_ids = [] #本次添加的id列表
        repeat_ids = []
        for result in results:
            id = result[1]
            text = result[2]
            if text == None:
                continue
            if id in Document_ids_func:
                #如果该文件已经保存过，则不保存到向量库中
                repeat_ids.append(id)
                continue
            doc_id = result[1]
            document = Document(
                page_content = text,
                metadata={'id': id, 'doc_id': doc_id, 'tag':tag, 'projectID':projectId}
            )
            documents.append(document)
            document_ids.append(id) 
            Document_ids_func.append(id) # 向全局id列表中添加   
        # 添加的documents不能为空
        if len(documents) > 0:
            document_ids = [str(num) for num in document_ids]
            Vector_store_func.add_documents(documents=documents, ids=document_ids)
            #保存修改后的doc id到本地
            utils.save_doc_ids(Document_ids_func,Vector_store_func_path)
            Logger.info("修改后的向量库与id列表保存成功")
            try:
                connection = utils.connect_database()
                cursor = connection.cursor()
                sql = "UPDATE ai_function_record SET status = 0 WHERE id IN ({})".format(', '.join(['%s'] * len(document_ids)))
                cursor.execute(sql, tuple(document_ids))
                connection.commit()
                Logger.info("数据库status修改成功")
            except Exception as e:
                Logger.info("数据库status修改失败")
                return jsonify({"status":500, "error":str(e)}), 500
            finally:
                Logger.info("关闭数据库连接")
                connection.close()
        if len(repeat_ids) > 0:
            # 将数字列表转换为字符串列表
            str_numbers = [str(num) for num in repeat_ids]
            str_repeat_ids = ",".join(str_numbers)
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("addFunction请求处理完成")
            return jsonify({"status": 200, "tag": tag, "projectID":projectId,"repeat ids": str_repeat_ids,"total functions": len(document_ids), "time-consuming": total_time}), 200
        else:
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("addFunction请求处理完成")
            return jsonify({"status": 200, "tag": tag, "projectID":projectId,"repeat ids": None, "total functions": len(document_ids),"time-consuming": total_time}), 200
#接口3    
@app.route("/deleteText", methods=['POST'])    
def delete_text():
    """从向量数据库中删除文本"""
    start_time = time.time()
    Logger.info("接受到deleteText请求：")
    form = utils.IdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":500, "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        ids = form.ids.int_list
        Logger.info(f"删除的id列表：{ids}")
        # 根据id，从向量数据库中读取数据
        delete_ids = []
        for id in ids:
            if id in Document_ids:
                # 只能删除向量库中存在的文档
                delete_ids.append(id)
                Document_ids.remove(id) # 删除该id
        if len(delete_ids) > 0:
            delete_ids = [str(num) for num in delete_ids]
            Vector_store.delete(ids = delete_ids)
            # 修改后均要保存
            # Vector_store.save_local(Vector_store_path, "langching_vector_store")
            utils.save_doc_ids(Document_ids,Vector_store_path)
            try:
                # 将存入向量库的文本在数据库中的状态修改为0
                connection = utils.connect_database()
                cursor = connection.cursor()
                sql = "UPDATE ai_document_sentence_record SET status = 1 WHERE id IN ({})".format(', '.join(['%s'] * len(delete_ids)))
                cursor.execute(sql, tuple(delete_ids))
                connection.commit()
                Logger.info("数据库status修改成功")
            except Exception as e:
                Logger.info("数据库status修改失败")
                return jsonify({"status":500, "error":str(e)}), 500
            finally:
                Logger.info("关闭数据库连接")
                connection.close()
            # 将数字列表转换为字符串列表
            str_numbers = [str(num) for num in delete_ids]
            str_delete_ids = ",".join(str_numbers)
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("delete Text 请求处理完成")
            return jsonify({"status": 200, "delete ids": str_delete_ids, "time-consuming": total_time}), 200
        else:
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("delete Text 请求处理完成")
            return jsonify({"status": 200, "delete ids": None, "time-consuming": total_time}), 200
#接口4
@app.route("/deleteFunction", methods=['POST'])    
def delete_func():
    """从向量数据库中删除功能点"""
    start_time = time.time()
    Logger.info("接受到deleteFunction请求：")
    form = utils.IdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":"500", "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        ids = form.ids.int_list
        Logger.info(f"删除的id列表：{ids}")
        delete_ids = []
        for id in ids:
            if id in Document_ids_func:
                # 只能删除向量库中存在的文档
                delete_ids.append(id)
                Document_ids_func.remove(id) # 删除该id
        if len(delete_ids) > 0:
            delete_ids = [str(num) for num in delete_ids]
            Vector_store_func.delete(ids = delete_ids)
            # 修改后均要保存
            # Vector_store_func.save_local(Vector_store_func_path, "langching_vector_store")
            utils.save_doc_ids(Document_ids_func,Vector_store_func_path)
            try:
                # 将存入向量库的文本在数据库中的状态修改为0
                connection = utils.connect_database()
                cursor = connection.cursor()
                sql = "UPDATE ai_function_record SET status = 1 WHERE id IN ({})".format(', '.join(['%s'] * len(delete_ids)))
                cursor.execute(sql, tuple(delete_ids))
                connection.commit()
                Logger.info("数据库status修改成功")
            except Exception as e:
                Logger.info("数据库status修改失败")
                return jsonify({"status":500, "error":str(e)}), 500
            finally:
                Logger.info("关闭数据库连接")
                connection.close()
            # 将数字列表转换为字符串列表
            str_numbers = [str(num) for num in delete_ids]
            str_delete_ids = ",".join(str_numbers)
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("delete Function 请求处理完成")
            return jsonify({"status": 200, "delete ids": str_delete_ids, "time-consuming": total_time}), 200
        else:
            end_time = time.time()
            total_time = end_time-start_time
            total_time = f"{total_time:.3f}s"
            Logger.info("delete Function 请求处理完成")
            return jsonify({"status": 200, "delete ids": None, "time-consuming": total_time}), 200
    
# 接口5 
@app.route('/matchText', methods=['POST'])
def match_text():
    """查询相似文本"""
    start_time = time.time()
    Logger.info("接受到matchText请求：")
    form = utils.IdtagIdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":"500", "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        projectId = int(form.projectId.data)
        tag = int(form.tag.data)
        projectIds = form.projectIds.int_list
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"待查重的项目id：{projectId}")
        Logger.info(f"指定查重的项目范围id: {projectIds}")
        sim_results= []
        # 根据id，从向量数据库中读取数据
        try:
            connection = utils.connect_database()
            cursor = connection.cursor()
            # TODO 待查重的文本其实应该从另一个表中查询，但是测试时就算了
            query = f"""
                SELECT
                    dr.id AS documentId,
                    dsr.id AS sentenceId,
                    dsr.sentence_content
                FROM
                    ai_document_record dr
                    INNER JOIN ai_document_paragraph_record dpr ON dpr.document_id = dr.id
                    INNER JOIN ai_document_sentence_record dsr ON dsr.paragraph_id = dpr.id
                WHERE
                    dr.project_id = {projectId}
                    AND dr.tag = {tag};
                """
            # sql = "SELECT `id`, `sentence_content`,`paragraph_id` FROM `ai_document_sentence_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            # cursor.execute(sql,tuple(ids))
            cursor.execute(query)
            results = cursor.fetchall()
        except Exception as e:
            Logger.info("数据库读取数据失败")
            return jsonify({"status":500, "error":str(e)}), 500
        finally:
            Logger.info("关闭数据库连接")
            connection.close()
        for result in results:
            id = result[1]
            text = result[2]
            # filter_conditions = {"tag": {"$eq": 1}}
            if -1 in projectIds:
                filter_conditions = {"$and":[{'tag':tag},{'projectID': {"$ne":projectId}}]}
            else:
                filter_conditions = {
                    "$and":[{'tag':tag},{'projectID': {"$ne":projectId}},{'projectID': {"$in":projectIds}}]
                }
            sims = Vector_store.similarity_search_with_relevance_scores(
                text,
                k=3,
                filter=filter_conditions
            )
            for sim, score in sims:
                score = round(score, 3) # 限定只取3位
                if score >= 0.5: # 向量相似度至少超过0.5才进行下一步计算，否则直接判定为不相似
                    if(str(id) == str(sim.metadata['id'])):
                        continue # 如果是id相同，说明同一段文本，排除
                    score_jaac = round(utils.compare_words(text, sim.page_content),3)
                    try:
                        # score_llm = 1
                        score_llm = utils.compare_llm(text, sim.page_content)
                    except Exception as e:
                        Logger.info(f"请求大模型出错：{e}")
                        score_llm = -1
                    score_all = utils.compute_score(score_llm, score_jaac, score)
                    if score_all> 0.1:
                        sim_res = (id, sim.metadata['id'], score_all)
                        sim_results.append(sim_res)
                        Logger.info(f"{id}: {text}\n*[score = {score}] [score_jaac={score_jaac}]  [score_all={score_all}] [score_llm={score_llm}]|{sim.page_content} |[{sim.metadata['id']}]\n-*6")
        str_result = ','.join(str(res) for res in sim_results)
        end_time = time.time()
        total_time = end_time-start_time
        total_time = f"{total_time:.3f}s"
        Logger.info("match Text 请求处理完成")
        return jsonify({"status": 200, "tag": tag, "match text result": str_result, "time-consuming": total_time}),200
# 接口6
@app.route('/matchTextFast', methods=['POST'])
def match_text_fast():
    """查询相似文本"""
    start_time = time.time()
    Logger.info("接受到matchTextFast请求：")
    form = utils.IdtagIdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":"500", "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        projectId = int(form.projectId.data)
        tag = int(form.tag.data)
        projectIds = form.projectIds.int_list
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"待查重的项目id：{projectId}")
        Logger.info(f"指定查重的项目范围id: {projectIds}")
        sim_results= []
        # 根据id，从向量数据库中读取数据
        try:
            connection = utils.connect_database()
            cursor = connection.cursor()
            # TODO 待查重的文本其实应该从另一个表中查询，但是测试时就算了
            query = f"""
                SELECT
                    dr.id AS documentId,
                    dsr.id AS sentenceId,
                    dsr.sentence_content
                FROM
                    ai_document_record dr
                    INNER JOIN ai_document_paragraph_record dpr ON dpr.document_id = dr.id
                    INNER JOIN ai_document_sentence_record dsr ON dsr.paragraph_id = dpr.id
                WHERE
                    dr.project_id = {projectId}
                    AND dr.tag = {tag};
            """

            # sql = "SELECT `id`, `sentence_content`,`paragraph_id` FROM `ai_document_sentence_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            # cursor.execute(sql,tuple(ids))
            cursor.execute(query)
            results = cursor.fetchall()
        except Exception as e:
            Logger.info("数据库读取数据失败")
            return jsonify({"status":500, "error":str(e)}), 500
        finally:
            Logger.info("关闭数据库连接")
            connection.close()
        for result in results:
            id = result[1]
            text = result[2]
            # version = result[3]
            # Logger.info(f"version: {version}")
            if -1 in projectIds:
                filter_conditions = {"$and":[{'tag':tag},{'projectID': {"$ne":projectId}}]}
            else:
                filter_conditions = {
                    "$and":[{'tag':tag},{'projectID': {"$ne":projectId}},{'projectID': {"$in":projectIds}}]
                }
            sims = Vector_store.similarity_search_with_relevance_scores(
                text,
                k=3,
                filter=filter_conditions
            )
            for sim, score in sims:
                score = round(score, 3) # 限定只取3位
                if score >= 0.5: # 向量相似度至少超过0.5才进行下一步计算，否则直接判定为不相似
                    if(str(id) == str(sim.metadata['id'])):
                        continue # 如果是id相同，说明同一段文本，排除
                    score_jaac = round(utils.compare_words(text, sim.page_content),3)
                    score_llm = -1 # 快速查重，不使用大模型
                    score_all = utils.compute_score(score_llm, score_jaac, score)
                    if score_all> 0.1:
                        sim_res = (id, sim.metadata['id'], score_all)
                        sim_results.append(sim_res)
                        Logger.info(f"{id}: {text}\n*[score = {score}] [score_jaac={score_jaac}]  [score_all={score_all}] [score_llm={score_llm}]|{sim.page_content} |[{sim.metadata['id']}]\n-*6")
        str_result = ','.join(str(res) for res in sim_results)
        end_time = time.time()
        total_time = end_time-start_time
        total_time = f"{total_time:.3f}s"
        Logger.info("match Text Fast请求处理完成")
        return jsonify({"status": 200, "tag": tag, "match text result": str_result, "time-consuming": total_time}),200
# 接口7
@app.route('/matchFunction', methods=['POST'])
def match_func():
    """查询相似功能点"""
    start_time = time.time()
    Logger.info("接受到matchFunction请求：")
    form = utils.IdtagIdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":"500", "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        projectId = int(form.projectId.data)
        tag = int(form.tag.data)
        projectIds = form.projectIds.int_list
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"待查重的项目id：{projectId}")
        Logger.info(f"指定查重的项目范围id: {projectIds}")
        sim_results= []
        try:
            connection = utils.connect_database()
            # 根据id，从向量数据库中读取数据
            cursor = connection.cursor()
            # TODO 待查重的文本其实应该从另一个表中查询，但是测试时就算了
            query = f"""
                SELECT
                    dr.id AS documentId,
                    dsr.id AS sentenceId,
                    dsr.function_point_description
                FROM
                    ai_document_record dr
                    INNER JOIN ai_function_record dsr ON dsr.document_id = dr.id
                WHERE
                    dr.project_id = {projectId}
                    AND dr.tag = {tag};
                """
            # sql = "SELECT `id`, `function_point_description`,`document_id` FROM `ai_function_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            # cursor.execute(sql,tuple(ids))
            cursor.execute(query)
            results = cursor.fetchall()
            Logger.info("从数据库读取待查重文本成功")
        except Exception as e:
            Logger.info("从数据库读取待查重文本失败")
            return jsonify({"status": 500, "error": str(e)}), 500
        finally:
            Logger.info("关闭数据库连接")
            connection.close()
        for result in results:
            id = result[1]
            text = result[2]
            filter_conditions = {
                "$and":[{'tag':tag},{'projectID': {"$ne":projectId}},{'projectID': {"$in":projectIds}}]
            }
            if -1 in projectIds:
                filter_conditions = {"$and":[{'tag':tag},{'projectID': {"$ne":projectId}}]}
                
            else:
                filter_conditions = {
                    "$and":[{'tag':tag},{'projectID': {"$ne":projectId}},{'projectID': {"$in":projectIds}}]
                }
            sims = Vector_store_func.similarity_search_with_relevance_scores(
                text,
                k=3,
                filter=filter_conditions #只查相同类型文档中的文本
            )
            for sim, score in sims:
                score = round(score, 3) # 限定只取3位
                if score >= 0.5: # 向量相似度至少超过0.5才进行下一步计算，否则直接判定为不相似
                    if(str(id) == str(sim.metadata['id'])):
                        continue # 如果是id相同，说明同一段文本，排除
                    score_jaac = round(utils.compare_words(text, sim.page_content),3)
                    try:
                        # score_llm = 1
                        score_llm = utils.compare_llm(text, sim.page_content)
                    except Exception as e:
                        Logger.info(f"请求大模型出错：{e}")
                        score_llm = -1
                    score_all = utils.compute_score(score_llm, score_jaac, score)
                    if score_all  > 0.1:
                        sim_res = (id, sim.metadata['id'], score_all)
                        sim_results.append(sim_res)
                        Logger.info(f"{id}: {text}\n*[score = {score}] [score_jaac={score_jaac}]  [score_all={score_all}] [score_llm={score_llm}]|{sim.page_content} |[{sim.metadata['id']}]\n-*6")
        str_result = ','.join(str(res) for res in sim_results)
        end_time = time.time()
        total_time = end_time-start_time
        total_time = f"{total_time:.3f}s"
        Logger.info("match Function 请求处理完成")
        return jsonify({"status": 200, "tag": tag, "match function result": str_result, "time-consuming": total_time}),200
# 接口8
@app.route('/matchFunctionFast', methods=['POST'])
def match_func_fast():
    """查询相似功能点"""
    start_time = time.time()
    Logger.info("接受到matchFunctionFast请求：")
    form = utils.IdtagIdsForm()
    if not form.validate_on_submit():
        # 如果验证失败，返回错误信息
        return jsonify({"status":"500", "error":str(form.errors)}), 500
    else:
        # 如果验证通过，可以访问转换后的整数列表
        projectId = int(form.projectId.data)
        tag = int(form.tag.data)
        projectIds = form.projectIds.int_list
        Logger.info(f"所属tag：{tag}")
        Logger.info(f"待查重的项目id：{projectId}")
        Logger.info(f"指定查重的项目范围id: {projectIds}")
        sim_results= []
        try:
            connection = utils.connect_database()
            # 根据id，从向量数据库中读取数据
            cursor = connection.cursor()
            # TODO 待查重的文本其实应该从另一个表中查询，但是测试时就算了
            query = f"""
                SELECT
                    dr.id AS documentId,
                    dsr.id AS sentenceId,
                    dsr.function_point_description
                FROM
                    ai_document_record dr
                    INNER JOIN ai_function_record dsr ON dsr.document_id = dr.id
                WHERE
                    dr.project_id = {projectId}
                    AND dr.tag = {tag};
                """
            # sql = "SELECT `id`, `function_point_description`,`document_id` FROM `ai_function_record`WHERE `id` IN ({})".format(', '.join(['%s'] * len(ids)))
            # cursor.execute(sql,tuple(ids))
            cursor.execute(query)
            results = cursor.fetchall()
            Logger.info("从数据库读取待查重文本成功")
        except Exception as e:
            Logger.info("从数据库读取待查重文本失败")
            return jsonify({"status": 500, "error": str(e)}), 500
        finally:
            Logger.info("关闭数据库连接")
            connection.close()
        Logger.info(f"results: {results}")
        for result in results:
            Logger.info(f"result: {result}")
            id = result[1]
            text = result[2]
            Logger.info(f"text: {text}")
            if -1 in projectIds:
                filter_conditions = {"$and":[{'tag':tag},{'projectID': {"$ne":projectId}}]}
            else:
                filter_conditions = {
                    "$and":[{'tag':tag},{'projectID': {"$ne":projectId}},{'projectID': {"$in":projectIds}}]
                }
            sims = Vector_store_func.similarity_search_with_relevance_scores(
                text,
                k=3,
                filter = filter_conditions #只查相同类型文档中的文本
            )
            for sim, score in sims:
                score = round(score, 3) # 限定只取3位
                if score >= 0.5: # 向量相似度至少超过0.5才进行下一步计算，否则直接判定为不相似
                    if(str(id) == str(sim.metadata['id'])):
                        continue # 如果是id相同，说明同一段文本，排除
                    score_jaac = round(utils.compare_words(text, sim.page_content),3)
                    score_llm = -1
                    score_all = utils.compute_score(score_llm, score_jaac, score)
                    if score_all  > 0.1:
                        sim_res = (id, sim.metadata['id'], score_all)
                        sim_results.append(sim_res)
                        Logger.info(f"{id}: {text}\n*[score = {score}] [score_jaac={score_jaac}]  [score_all={score_all}] [score_llm={score_llm}]|{sim.page_content} |[{sim.metadata['id']}]\n-*6")
        str_result = ','.join(str(res) for res in sim_results)
        end_time = time.time()
        total_time = end_time-start_time
        total_time = f"{total_time:.3f}s"
        Logger.info("match Function Fast请求处理完成")
        return jsonify({"status": 200, "tag": tag, "match function result": str_result, "time-consuming": total_time}),200

def shutdown_server(signum, frame):
    Logger.info('收到关闭信号，正在关闭服务器...')
    utils.stop_llm() # 关闭llm
    func = request.environ.get('werkzeug.server.shutdown')
    if func is not None:
        func()


if __name__ =='__main__':
    # 注册信号处理函数
    # signal.signal(signal.SIGINT, shutdown_server)
    # signal.signal(signal.SIGTERM, shutdown_server)
    app.run(host='0.0.0.0', port=2222)