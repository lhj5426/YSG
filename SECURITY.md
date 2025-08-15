机翻自用 非上传到互联网分享  的模型正确使用方法
1 使用[CVHub520/X-AnyLabeling ](https://github.com/CVHub520/X-AnyLabeling) 跑检测并修正 导出 YOLO格式数据

https://github.com/user-attachments/assets/de490d74-fd5d-463b-baed-84c3007d0b30

2 使用脚本生成训练数据 可以在看漫画的时候直接收集训练数据 


https://github.com/user-attachments/assets/11d9d598-ad0c-46e2-9a5a-2119d1ad38d7

3使用脚本生成伪造BL https://github.com/dmMaze/BallonsTranslator 配置文件JSON的 数据

https://github.com/user-attachments/assets/21d877bb-78a8-4f30-8615-ff995093f721

4把数据文件夹放到图片同级目录下并用脚本生成BL https://github.com/dmMaze/BallonsTranslator 伪造配置文件

5使用BL https://github.com/dmMaze/BallonsTranslator 导入配置 并执行OCR

https://github.com/user-attachments/assets/36c114ef-a82a-4186-a47f-ac41d46c072c

6使用BL https://github.com/dmMaze/BallonsTranslator OCR后的文件生成 imagetrans https://www.basiccat.org/zh/imagetrans/ 的配置文件

https://github.com/user-attachments/assets/4ae332a6-8d7d-487e-8afc-2c071bf7d5f8

7使用imagetrans https://www.basiccat.org/zh/imagetrans/ 打开配置文件 并使用正则查找 是否有没有OCR到的空字幕块

https://github.com/user-attachments/assets/3d5b10d2-d70a-4be1-9c12-a9d769309498

8之后根据漫画阅读顺序设置排序方式 并进行排序

https://github.com/user-attachments/assets/cebef8a5-d217-481d-8103-d2bd186c6c81

9排序之后进行文本块的合并

https://github.com/user-attachments/assets/4cf875d6-17d7-433d-afc3-9020584c8fae

10导出纯文本TXT

https://github.com/user-attachments/assets/4f75bca8-b053-4186-a61f-0dd8564bbebf

11使用 KeywordGacha https://github.com/neavo/KeywordGacha 导入文本 生成术语表

https://github.com/user-attachments/assets/b9280d9f-f5e4-4ffc-b32f-5a4d2fa2cb21

12使用 LinguaGacha https://github.com/neavo/LinguaGacha 或者 AiNiee https://github.com/NEKOparapa/AiNiee
导入并修正术语 并进行翻译

https://github.com/user-attachments/assets/2c5c0c8f-6114-4c05-8ab2-e4a11695f460

13找到翻译后的TXT并使用脚本将TXT改成 imagetrans https://www.basiccat.org/zh/imagetrans/ 的导入格式 

https://github.com/user-attachments/assets/6f40a108-e242-4d06-bab0-55261fa4bb62

14选择只导入译文

https://github.com/user-attachments/assets/dbefde75-38ad-42ea-b830-340b5ca30f00

15开始阅读

https://github.com/user-attachments/assets/144ff616-099a-40d2-9b32-add3a0b55c9d

以上操作可以批量执行
