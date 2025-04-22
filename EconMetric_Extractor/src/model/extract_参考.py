import re
import os
import pickle
from modelscope import snapshot_download
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams

# GLM-4-9B-Chat-1M
# max_model_len, tp_size = 1048576, 4

# GLM-4-9B-Chat
# 如果遇见 OOM 现象，建议减少max_model_len，或者增加tp_size
max_model_len, tp_size = 131072, 1
model_dir = snapshot_download("ZhipuAI/glm-4-9b-chat")

tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
llm = LLM(
    model=model_dir,
    tensor_parallel_size=tp_size,
    max_model_len=max_model_len,
    trust_remote_code=True,
    enforce_eager=True,
    # GLM-4-9B-Chat-1M 如果遇见 OOM 现象，建议开启下述参数
    # enable_chunked_prefill=True,
    # max_num_batched_tokens=8192
)

stop_token_ids = [151329, 151336, 151338]
sampling_params = SamplingParams(
    temperature=0, max_tokens=1024, stop_token_ids=stop_token_ids
)

system_prompt = """
拜托你把事情做好，否则我就会被解雇。如果没有这份工作，我的家人就会饿死。
预计生产总值是对过去的总结，预期生产总值是对未来的预估，请找出与预期对应的生产总值。
你只需要生成Reason和Output，不要生成下一个新的Input。
在收到用户输入的Input后，逐步进行思考，在Reason中给出思考过程，在Output中给出答案。
参考下述例子，从给出的Input中提取出今年生产总值的预期增长值是多少？
若上下文中没有提到就返回null，若有其他表述就节选出对应的描述文本。
按照下述提供的json格式返回结果。

Input: 抚顺市2004年文件节选：2004年的主要预期目标是:国内生产总值实现360亿元，增长14.5％
Reason: 当前年份是2004年，文本中提到2004年国内生产总值预期增长14.5％。
Output: {"city":"抚顺市", "year":"2004", "GDP_growth":"14.5%"}

Input: 上海市1895年文件节选：初步核算，全市生产总值比上年增长１１．１％，规模以上工业增加值增长２１．７％，农民人均纯收入增长１０．２％，年初确定的主要预期目标和各项工作任务全面超额完成\n今年经济社会发展的主要预期目标是：生产总值增长１２％，全社会固定资产投资增长２０％，'
Reason: 全市生产总值比上年增长１１．１％，这是去年的总结；生产总值增长１２％，这才是今年的预期；所以要返回12%。
Output: {"city":"上海市", "year":"1895", "GDP_growth":"12%"}

Input: 郴州市2011年文件节选：主要预期目标是：到2015年，全市生产总值2240亿元，年均增长13%以上，人均生产总值超过4万元\n主要预期目标是：地区生产总值增长14%
Reason: 到2015年，全市生产总值2240亿元。今年是2011年，2015年的预期不是所需要的结果。主要预期目标是：地区生产总值增长14%。这才是所需要的结果，所以返回14%。
Output: {"city":"郴州市", "year":"2011", "GDP_growth":"14%"}

Input: 聊城市2024年文件节选：预计全市生产总值超过2900亿元、增长6%，高于预期目标\n经济社会发展主要预期目标是: 地区生产总值增长5.5%以上，一般公共预算收入增长5.5%，固定资产投资增长7%，
Reason: 预计全市生产总值超过2900亿元，这是对过去的总结。经济社会发展主要预期目标是: 地区生产总值增长5.5%以上，这才是所需要的结果，故返回5.5%。
Output: {"city":"聊城市", "year":"2024", "GDP_growth":"5.5%"}

Input: {filename}年文件节选：{content}
Reason: 
""".strip()


## 收集要进行推理的数据集

def split_sentence_by_punctuation(sentence):
    pattern = r"[。？！；;！]"
    parts = re.split(pattern, sentence)
    parts = [part for part in parts if part]
    return parts


def read_txt_files_in_folder(folder_path):
    """
    读取指定文件夹下的所有.txt文件，并将每个文件的文本内容按行分割成列表。

    :param folder_path: 包含.txt文件的文件夹路径
    :return: 一个字典，键为文件名（不含扩展名），值为文件内容的行列表
    """
    txt_files = {}
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()
                # 读取文件的所有内容，将其拆分成句子
                lines = split_sentence_by_punctuation(text)
                target = []
                for line in lines:
                    if "预期目标" in line and "生产总值" in line and "增长" in line:
                        line = line.strip()
                        # 删除一些乱码字符
                        for word in ["\u3000", "xa0", "\n"]:
                            line = line.replace(word, "")
                        target.append(line.strip())
                txt_files[os.path.splitext(filename)[0]] = target
    return txt_files


def format_prompt(system_prompt, kw):
    res = system_prompt.replace("{content}", "\n".join(files_content[kw]))
    return res.replace("{filename}", kw)


folder_path = "city"
files_content = read_txt_files_in_folder(folder_path)

prompts = []
for k, v in files_content.items():
    p = format_prompt(system_prompt, k)
    prompts.append([{"role": "user", "content": p}])

inputs = tokenizer.apply_chat_template(
    prompts, tokenize=False, add_generation_prompt=True
)

outputs = llm.generate(prompts=inputs, sampling_params=sampling_params)

# ## 保存预测结果
with open("vllm_glm4_infer.pkl", "wb") as f:
    # 序列化对象并保存到文件
    pickle.dump(outputs, f)