import os
import re
import pdfplumber
import logging

log_fmt = "%(asctime)s - %(levelname)s: %(message)s"
logging.basicConfig(format=log_fmt)
logging.getLogger().setLevel(logging.INFO)


def contains_digit_filters(sentence):
    """
    判断句子中是否包含数字
    """
    for char in sentence:
        if char.isdigit():
            return True
    return False


def cut_txt2sents(input_file, output_file, *args):
    """
    这部分处理由pdf转的txt文件，再将txt文本按照句号。切分
    由于pdf转的txt文件，其文件内容很乱，需要进行一些处理
    * args: 过滤器
        针对句子的过滤器
    """
    # 删除
    delete_list = ["\xa0", "\t", "\u3000", " ", "﻿", " ", " ", "​", "目\n录\n", "\n"]

    if input_file.endswith(".txt"):
        with open(input_file, "r", encoding="utf-8") as f:
            text = f.read()

        for char in delete_list:
            text = text.replace(char, "")

        text = text.replace(";", "。")
        text = text.replace("；", "。")

        ## 本来按照\n切分最好，但是pdf转txt后，其中包含很多的\n，所以无法使用\n提前切分
        # texts = text.split('\n')

        data = text.split("。")

        # 过滤器
        for arg in args:
            data = filter(arg, data)

        with open(output_file, "w", encoding="utf-8", errors="ignore") as f:
            f.write("\n".join(data))


class PdfConvertText:
    def __init__(self, source_fold, output_fold, filters: list = []):
        self.dir_path = dir
        self.source_fold = source_fold
        self.output_fold = output_fold
        self.filters = filters
        os.makedirs(self.output_fold, exist_ok=True)

    def check_pdf_content(self, file_path):
        """
        检查pdf文件是否有内容
        有内容返回True，否则是扫描版返回False
        """
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                if page.extract_text():
                    return True
        return False

    def delete_page_num(self, text):
        """
            删除页码
        :param text:
        :return:
        """
        page_nums = [
            r"\n- \d+ -( *?)\n",
            r"\n— \d+ —( *?)+\n",
            r"\n\d+( *?)\n",
            r"\nI+( *?)\n",
        ]

        patterns = [re.compile(pattern) for pattern in page_nums]
        for pattern in patterns:
            text = pattern.sub("", text)
        return text

    def trans_pdf_text(self, input_file, output_file, is_delete_page=True):
        """
        把pdf文件转为txt，删除页码，保存到output_file
        """
        # 不支持扫描的PDF
        if self.check_pdf_content(input_file) == False:
            logging.info(f"输入{input_file}为扫描版本")
            return

        res = []
        with pdfplumber.open(input_file) as pdf:
            for page in pdf.pages:
                res.append(page.extract_text())

        text = "".join(res)
        if is_delete_page:
            text = self.delete_page_num(text)
        with open(output_file, "w", encoding="utf-8", errors="ignore") as f:
            f.write(text)

    def trans_folder_pdf2txt(self):
        """
            把某目录下pdf文件转为txt
        :return:
        """
        for file in os.listdir(self.source_fold):
            if not file.endswith(".pdf"):
                continue
            file_name = os.path.join(self.source_fold, file)
            output_file = os.path.join(self.output_fold, file.replace(".pdf", ".txt"))
            self.trans_pdf_text(file_name, output_file)


if __name__ == "__main__":
    process = PdfConvertText(
        source_fold="data/pdf_folder",
        output_fold="data/pdf2text",
    )
    process.trans_folder_pdf2txt()


# filters=[contains_digit_filters],