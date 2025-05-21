# <div align="center">YSG</div>

<div align=center>
<img src="https://github.com/user-attachments/assets/0439e6bf-c256-4706-a846-1043643d4cc1" width="256" height="256">
</div>

我的频道

淫叔馆TG频道
https://t.me/yinshuguan

![image](https://github.com/user-attachments/assets/31755751-1c89-4484-8d1a-98e6fc95d079)

使用[Hitomi-Downloader](https://github.com/KurtBestor/Hitomi-Downloader) 手动采集E站每天更新的画廊


![image](https://github.com/user-attachments/assets/74787557-c5ab-4b9d-800b-e96f79d24c23)



黑白同人志3万3千多页 其余全部是画师CG全彩图片 我主要看全彩CG着重训练的也是全彩CG图

以及少量 [survivemore生存社PPT视频](https://www.appetite-game.com/survivemore/001_product.html)  文字区域切片 为了可以兼容硬字幕提取 

少量动漫双语字幕图片文字区域切片 为了硬字幕提取 横向文字图片数据

少量dlsite 上的 ASMR音声商品宣传介绍图图片 为了数据的多样性 

使用 [X-AnyLabeling](https://github.com/CVHub520/X-AnyLabelin) 

排除各种现有OCR技术无法识别的拟声词 （我都看机翻了我还在乎你拟声词吗？）


模型已上传到 https://huggingface.co/YSGforMTL/YSGYoloDetector

 视频演示



https://github.com/user-attachments/assets/845fde93-3128-41e3-8a2d-dbd971fb2e3c






BallonsTranslator 原来的CTD


https://github.com/user-attachments/assets/c3f1feca-338e-4df0-b823-10ddc424ce1f


BallonsTranslator 现在的我训练的YSGyolo




https://github.com/user-attachments/assets/b108637e-44ea-4228-9c67-d6a4d789aade

ImageTrans 原来自然场景检测



https://github.com/user-attachments/assets/35206b33-d9eb-4933-ab74-81e63fee33d2


ImageTrans 现在我训练的yolo



https://github.com/user-attachments/assets/ff6234c1-3211-4a33-ae3a-872213eae99f

看着不那么闹心了 现在就算是跑上千页的 手动修正也不会那么累了

有的精度高的时候根本就不需要手动修正


一个人没日没夜精确标注9个月

5个标签
balloon
qipao
fangkuai
changfangtiao
kuangwai

总计22万2千3百80张图片 97.3G数据集  有零有整的 标吐了 实在是不想再标了

![dopus_2025年04月06日04点45分31秒958](https://github.com/user-attachments/assets/a9db0bf5-e61b-4a43-9a22-681b86f6a902)

![dopus_2025年04月06日04点47分18秒052](https://github.com/user-attachments/assets/468344fd-f36a-49e3-8682-5f819a8fd059)

![dopus_2025年04月06日04点48分04秒875](https://github.com/user-attachments/assets/c2dc4b98-59fd-4151-8303-1d81d2842643)



在A100 64G显卡上进行训练

![image](https://github.com/user-attachments/assets/085967c1-b62b-4968-8d21-bb245093ea8d)

![image](https://github.com/user-attachments/assets/343cd3c0-4d00-49ca-ac49-636f3f37df78)

![WGestures_2025年04月13日20点52分11秒491](https://github.com/user-attachments/assets/15d914db-8969-4823-b365-4f7828195c58)

![WGestures_2025年04月10日15点46分15秒321](https://github.com/user-attachments/assets/96702ad7-e4f4-4690-95c4-4daab1dc3f28)

专门为 [ImageTrans](https://github.com/xulihang/ImageTrans-docs) 训练的
图片文字检测模型

另外 本模型也已实装在

开源的有GUI的漫画软件BallonsTranslator上

https://github.com/dmMaze/BallonsTranslator

感谢大佬支持并实装

2025年04月25日

使用 https://docs.ultralytics.com/zh/models/rtdetr/#usage-examples

百度百度RT-DETR 使用27595张图 总数据量的10%左右

![WGestures_2025年04月24日23点07分24秒078](https://github.com/user-attachments/assets/d7f44877-b623-4301-93cf-138d7a00f601)

 训练的模型

![image](https://github.com/user-attachments/assets/693c6ae5-f520-4f14-9b4c-1de760c85357)

![image](https://github.com/user-attachments/assets/aec46bbc-8440-43b1-891e-37e8ca99f3f9)


检测效果在一些漫画上效果要比 yoloV11用22万张训练的效果要好

总结出来个道理 数据量不在多少 而在是否选对了训练的模型 

2025年05月

最近在解决的问题

因为我本身不懂代码 就是看漫画不爽总要在翻译的时候先去处理一下拟声词

所以打算自己训练一个模型去干掉拟声词减少每次喂给AI翻译之前都要删半天拟声词的窘境

所以大树底下好乘凉 直接在大佬的开发的软件的基础上上训练一个自己的识别模型就好了

但是当模型训练好之后 遇到了新的问题

![image](https://github.com/user-attachments/assets/085e7f9d-bfb8-49bc-ab7d-de095d7cc474)

那就是和ocr不兼容

我的模型一共有 6个标签
balloon
qipao
fangkuai
changfangtiao
kuangwai
other

唯独 qipao 是一次框选多行

这就导致 有时候 多行文本OCR 会O不全

![image](https://github.com/user-attachments/assets/1335e7c8-872b-4ead-9b5a-64cbf726af98)

只有一条文字 一个矩形 才可以进行OCR识别

现在正则调整数据的所有气泡为一条一个矩形

这样就不会出现OCR不了 或者OCR不全的问题了

正在解决中......



# 感谢以下

图片翻译器
https://github.com/xulihang/ImageTrans-docs

数据标注工具
https://github.com/CVHub520/X-AnyLabeling

本子下载器
https://github.com/KurtBestor/Hitomi-Downloader

低画质图片数据来源
https://hitomi.la/

ultralytics (YOLOV11)
https://github.com/ultralytics/ultralytics



Quick input 使得鼠标可以像素级精确移动
https://github.com/ChiyukiGana/Quickinput

obs-studio
https://github.com/obsproject/obs-studio

X-AnyLabeling不能显示当前页面标签数量
用OBS采集显示器实现一个伪标签数量显示功能
好能直观的知道当前页面上有多少个标签 
![image](https://github.com/user-attachments/assets/b027f537-5187-4fab-b39f-b545f5780bf3)


LiveSplit 一个游戏速通计时器 用于记录每一本标注的时间和每天花费在标注上的总时间
https://livesplit.org



