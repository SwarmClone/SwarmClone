## 模型文件

此目录下存放 Live2D 模型文件，此目录下形似 xxx.json 的文件均被认为是一个模型的导入文件。具体格式如下：
```json
{
    "name": "模型名称",
    "path": "相对于本目录的模型文件（.model3.json/.model.json）路径"
}
```
注意 `version` 项填入一个整数2或3：
- 若模型文件为 *.model3.json 则 `version` 项填入 3
- 若模型文件为 *.model.json 则 `version` 项填入 2

**使用在此目录下的所有模型文件均须遵守其版权声明和使用协议！**
