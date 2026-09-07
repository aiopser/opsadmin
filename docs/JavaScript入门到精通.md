# JavaScript 入门到精通 · 六篇合集

> 本合集由《04_JavaScript入门到精通》系列 **6 篇教程**合并而成，涵盖 JavaScript 基础语法、函数与对象、BOM、DOM 编程、页面特效与高级进阶。点击目录可快速跳转。

## 目录

1. [JavaScript基础语法](#p1)
    - [一、JavaScript概述](#p1-1)
    - [二、JavaScript变量和数据类型](#p1-2)
    - [三、JavaScript运算符和表达式](#p1-3)
    - [四、JavaScript流程控制语句](#p1-4)
    - [课后习题](#p1-5)
2. [JavaScript函数与对象](#p2)
    - [一、JavaScript函数](#p2-1)
    - [二、JavaScript对象](#p2-2)
    - [三、JavaScript内置对象](#p2-3)
    - [课后习题](#p2-4)
3. [JavaScript BOM编程](#p3)
    - [一、BOM概述](#p3-1)
    - [二、window对象](#p3-2)
    - [三、History对象](#p3-3)
    - [四、Location 对象](#p3-4)
    - [五、Screen 对象](#p3-5)
    - [六、Navigator 对象](#p3-6)
    - [七、Frames对象](#p3-7)
4. [JavaScript DOM编程（基础篇）](#p4)
    - [一、JavaScript DOM 概述](#p4-1)
    - [二、JavaScript节点与节点树](#p4-2)
    - [三、JavaScript获取HTML标签元素](#p4-3)
    - [四、JavaScript操作标签内容](#p4-4)
    - [五、JavaScript操作标签属性](#p4-5)
    - [六、JavaScript Document对象属性一览](#p4-6)
    - [七、JavaScript获取层次节点](#p4-7)
    - [八、JavaScript操作节点](#p4-8)
5. [JavaScript DOM编程（特效篇）](#p5)
    - [一、JavaScript操作表格](#p5-1)
    - [二、JavaScript事件（重点）](#p5-2)
    - [三、JavaScript操作CSS样式](#p5-3)
    - [四、offset、client、scroll三大家](#p5-4)
    - [五、动画效果](#p5-5)
6. [JavaScript 高级](#p6)
    - [一、浏览器深入解析](#p6-1)
    - [二、正则表达式](#p6-2)
    - [三、JavaScript面向对象编程](#p6-3)
    - [四、函数进阶](#p6-4)
    - [八、附录](#p6-5)

---

<a id="p1"></a>

# 第1篇 · JavaScript基础语法

---

<a id="p1-1"></a>
# 一、JavaScript概述

## 1.1、JavaScript可以做什么

### 1.1.1、页面的各种动画效果

![1572771624838](images01_base/1572771603647.png)

### 1.1.2、页面的点击/移入响应

![1572771664195](images01_base/1572771664195.png)

![1572771720721](images01_base/1572771720721.png)

### 1.1.3、对客户端数据进行验证

![1572771753671](images01_base/1572771753671.png)

### 1.1.4、各种页面小游戏

![1572771778860](images01_base/1572771778860.png)

### 1.1.5、用途总结

> 嵌入动态文本于HTML页面。
>
> 对浏览器事件做出响应(对于用户的操作给予响应)。
>
> 读写HTML元素。
>
> 在数据被提交到服务器之前验证数据(客户端数据校验)。
>
> 检测访客的浏览器信息。
>
> 控制cookies，包括创建和修改等。
>
> 基于Node.js技术进行服务器端编程。

```html
JavaScript 发展到现在几乎无所不能。
1. 网页特效

2. 服务端开发(Node.js)

3. 命令行工具(Node.js)

4. 桌面程序(Electronjs)

5. App(Cordova)

6. 控制硬件-物联网(Ruff)

7. 游戏开发(cocos2d-js)
```

## 1.2、Why JavaScript

类似于JavaScript的语言有很多，比如: 微软推出的JScript，CEnvi推出的 ScriptEase

![1572771941519](images01_base/1572771941519.png)

![1572772005078](images01_base/1572772005078.png)

1、所有主流浏览器都支持JavaScript(支持程度广)。

2、目前，全世界大部分网页都使用JavaScript(用户群体广)。

3、它可以让网页呈现各种动态效果，做为一个Web开发师，如果你想提供漂亮的网页、**令用户满意**的上网体验，JavaScript是必不可少的工具(特点)。

4、易学性，学习环境无外不在，只要有文本编辑器，就能编写JavaScript程序。它是基于Java简化设计而来。

## 1.3、JavaScript基础概述

**JavaScript是一种解释型或即时编译型的高级编程语言，虽然它是作为开发Web页面的脚本语言而出名的，但是它也被用到了很多非浏览器环境中，JavaScript 基于原型编程、多范式的动态脚本语言，并且支持面向对象、命令式和声明式（如函数式编程）风格。**

**什么是脚本语言?**

```html
脚本语言是为了缩短传统的编写-编译-运行（edit-compile-run）过程而创建的计算机语言。

一个脚本通常是解释执行而非编译。脚本语言通常都有简单、易学、易用的特性，目的就是希望能让程序员快速完成程序的编写工作。

用最简单的语言总结一下，脚本语言就是，边解释边运行，非脚本语言，整体编译后，再运行。脚本语言必须运行到错误的地方，才会报错，而非脚本语言，在编译的时候，会报错。
```

**什么是基于原型编程?**

```html
基于原型的编程是面向对象编程的一种形式，通过复制已经存在的原型对象来实现面向对象，无与基于类的编程较大的区别是没有Class关键字，但是有类的概念。基于原型的编程也可以理解成基于实例的编程。

基于原型的系统可以在程序运行时对原型进行修改，基于类(Java， C+)的语言则很难实现这一点。
```

**什么是编程范式?**

```html
编程范式是程序语言背后的思想。代表了程序设计者认为程序应该如何被构建和执行的看法。常见的编程范式有：过程式（命令式），面向对象，函数式，泛型编程等。

和C++等语言类似，JS支持多范式（paradigms）编程。我们常常混合这些范式来完成一些大型Web项目。

JS支持3种编程范式：命令式、面向对象和函数式。
```

**JavaScript的解释器被称为JavaScript引擎，为浏览器的一部分，广泛用于客户端的脚本语言，最早是在HTML（标准通用标记语言下的一个应用）网页上使用，用来给HTML网页增加动态功能。**

JavaScript主要用于HTML的页面，嵌入在HTML的源码中。

JavaScript 是互联网上最流行的脚本语言，这门语言可用于 HTML 和 web，更可广泛用于服务器、PC、笔记本电脑、平板电脑和智能手机等设备。它存在于全世界所有 Web 浏览器中，能够给页面添加动态效果和动态交互。

JavaScript最初的目的是为了处理表单的验证操作。

## 1.4、JavaScript组成部分

![1572772904781](images01_base/1572772904781.png)

```html
JavaScript是由ECMAScript、文档对象模型（Document Object Model:DOM）、浏览器对象模型（Brower Object Model:BOM）三部分构成。

ECMAScript，描述了该语言的基础语法和基本对象(包含内置对象)，JavaScript的核心，描述了语言的基本语法(变量、运算符、表达式、流程控制语句、array等)和数据类型(数字、字符串、布尔、函数、对象(obj、[]、{}、null)、未定义)，ECMAScript是一套标准.

文档对象模型（DOM），描述处理网页内容的方法和接口。通过 DOM，可以访问所有的 HTML 元素，连同它们所包含的文本和属性，可以对其中的内容进行修改和删除，同时也可以创建新的元素；DOM（文档对象模型）是 HTML 和 XML 的应用程序接口（API）。DOM 将把整个页面规划成由节点层级构成的文档。HTML 或 XML 页面的每个部分都是一个节点的衍生物。

浏览器对象模型（BOM），描述与浏览器进行交互的方法和接口。BOM提供了独立于内容而与浏览器窗口进行交互的对象，例如可以移动，调整浏览器大小的window对象，可以用于导航的location对象与history对象，可以获取浏览器，操作系统与用户屏幕信息的navigator与screen对象。
```

## 1.5、JavaScript特点

JavaScript是一种属于浏览器的脚本语言，已经被广泛用于Web应用开发，常用来为网页添加各式各样的动态功能，为用户提供更流畅美观的浏览效果。通常JavaScript脚本是通过嵌入在HTML中来实现自身的功能的(但写成单独的js文件有利于结构和行为的分离)。

![1572773230282](images01_base/1572773230282.png)

**弱类型** :  声明变量无需指定数据类型，统一使用var来声明变量；声明的变量可以存储任意类型的值；

**解释性** : JavaScript是一种解释型的脚本语言，C、Java等语言先编译后执行，而JavaScrip源代码不需要经过编译，直接在浏览器上运行时被解释。

**基于对象** : Javascript是一种基于对象的语言，能运用自己已经创建了的对象，许多功能可以来自于脚本环境中对象的方法与脚本的相互作用。

**简单性** : JavaScript语言中采用的是弱类型的变量类型，对使用的数据类型未做出严格的要求，是基于Java基本语句和控制的脚本语言，其设计简单紧凑。

**事件驱动(Event Driven) 和动态性** : JavaScript是一种采用事件驱动（所谓事件驱动，指的是在页面执行了某种操作所产生的动作，此动作称为“事件”。）的脚本语言，它不需要经过Web服务器就可以对用户的输入做出响应。在访问一个网页时，鼠标在网页中进行鼠标点击或上下移、窗口移动等操作JavaScript都可直接对这些事件给出相应的响应（针对于用户在页面中的操作，都是基于事件驱动）。

**跨平台性**：JavaScript脚本语言不依赖于操作系统，仅需要浏览器的支持。因此一个JavaScript脚本在编写后可以带到任意机器上使用，前提上机器上的浏览器支 持JavaScript脚本语言，目前JavaScript已被大多数的浏览器所支持。

不同于服务器端脚本语言，例如PHP与ASP，**JavaScript主要被作为客户端脚本语言在用户的浏览器上运行，不需要服务器的支持**。所以在早期程序员比较青睐于JavaScript以减少对服务器的负担，而与此同时也带来另一个问题：安全性。

HTML5的出现更是突出了JavaScript的重要性，例如HTML5的绘图支持、本地存储、离线应用、客户端通信等，都大量使用了JavaScript。

而随着服务器的强壮，虽然程序员更喜欢运行于服务端的脚本以保证安全，但JavaScript仍然以其跨平台、容易上手等优势大行其道。同时，有些特殊功能（如AJAX）必须依赖Javascript在客户端进行支持。随着引擎如V8和框架如Node.js的发展，及其事件驱动及异步IO等特性，JavaScript逐渐被用来编写服务器端程序。

## 1.6、JavaScript历史

在1995年时，由Netscape(网景)公司的Brendan Eich(布兰登·艾奇)，在网景导航者浏览器上首次设计实现而成。JavaScript是甲骨文公司的注册商标。

Netscape在最初将其脚本语言命名为LiveScript，后来因为Netscape与Sun合作，Netscape管理层希望它外观看起来像Java，因此取名为JavaScript。但实际上它的语法风格与Self及Scheme较为接近。

JavaScript最初受Java启发而开始设计的，目的之一就是“看上去像Java”，因此语法上有类似之处，一些名称和命名规范也借自Java。但JavaScript的主要设计原则源自Self和Scheme。

JavaScript与Java名称上的近似，是当时Netscape为了营销考虑与Sun微系统达成协议的结果。为了取得技术优势，微软推出了JScript，CEnvi推出ScriptEase，与JavaScript同样可在浏览器上运行。

为了统一规格，因为JavaScript兼容于ECMA标准，因此也称为ECMAScript。为了互用性，Ecma国际（前身为欧洲计算机制造商协会）创建了ECMA-262标准（ECMAScript）。两者都属于ECMAScript的实现。尽管JavaScript作为给非程序人员的脚本语言，而非作为给程序人员的脚本语言来推广和宣传，但是JavaScript具有非常丰富的特性。

发展初期，JavaScript的标准并未确定，同期有Netscape的JavaScript，微软的JScript和CEnvi的ScriptEase三足鼎立。1997年，在ECMA（欧洲计算机制造商协会）的协调下，由Netscape、Sun、微软、Borland组成的工作组确定统一标准：ECMA-262。

JavaScript 已经由 ECMA（欧洲电脑制造商协会）通过 ECMAScript 实现语言的标准化。

ECMA这个组织的目标是评估，开发和认可电信和计算机标准。

| 年份 | 名称           | 描述                                              |
| ---- | -------------- | ------------------------------------------------- |
| 1997 | ECMAScript 1   | 第一个版本                                        |
| 1998 | ECMAScript 2   | 版本变更                                          |
| 1999 | ECMAScript 3   | 添加正则表达式 添加 try/catch                     |
|      | ECMAScript 4   | 没有发布                                          |
| 2009 | ECMAScript 5   | 添加 "strict mode"，严格模式 添加 JSON 支持       |
| 2011 | ECMAScript 5.1 | 版本变更                                          |
| 2015 | ECMAScript 6   | 添加类和模块                                      |
| 2016 | ECMAScript 7   | 增加指数运算符 (**) 增加 Array.prototype.includes |

> ECMAScript 6 也称为 ECMAScript 2015。
>
> ECMAScript 7 也称为 ECMAScript 2016。

## 1.7、JavaScript的引入方式

HTML 中的脚本必须位于 `<script>`与`</script>` 标签之间。

脚本可被放置在 HTML 页面的` <body>` 和 `<head>` 部分中。

引入JavaScript需要使用script标签：

​	```<script>```标签用于定义客户端脚本，script 元素即可包含脚本语句，又可通过 src 属性指向外部脚本文件。

如果想在页面上使用JavaScript，必须使用```<script>```标签，把JavaScript源码放入```<script>```和```</script>```之间。

`<script>`标签属性:

​	type：指定脚本的类型。

​	src：指定外部脚本的url。

如需在 HTML 页面中插入 JavaScript，请使用 <script> 标签。

`<script>` 和 `</script>` 会告诉 JavaScript 在何处开始和结束。

`<script>` 和 `</script>` 之间的代码行包含了 JavaScript:

```html
<script>
	//定义JS代码
</script>

//引入外部JS文件
<script src="url"></script>
```

浏览器会解释并执行位于`<script>` 和 `</script>`之间的 JavaScript 代码 .

```html
那些老旧的实例可能会在 <script> 标签中使用 type="text/javascript"。现在已经不必这样做了。
    
JavaScript 是所有现代浏览器以及 HTML5 中的默认脚本语言。
```

### 1.7.1、行内引入JavaScript

在标签事件属性中填写JavaScript代码或调用函数时，调用函数时不是 事件=函数名， 而是 事件=函数名+()

```html
<button onclick="alert('我是一个警告框')" type="button">点击这里</button>
```

```html
<head>
    <script>
        function myfunction(){
            document.getElementById("demo").innerHTML="onclick事件触发";
        }
	</script>
</head>
<body>
    <h1 id="demo">一个段落</h1>
    <button onclick="myfunction()" type="button">点击这里</button>
</body>
```

### 1.7.2、内部引入JavaScript

您可以在 HTML 文档中放入不限数量的脚本。

脚本可位于 HTML 的```<body>``` 或 ```<head>``` 部分中，或者同时存在于两个部分中。

通常的做法是把函数放入```<head>``` 部分中，或者放在页面底部。这样就可以把它们安置到同一处位置，不会干扰页面的内容。

```html
<!DOCTYPE html>
<html>
<head>
<script>
    function myFunction(){
        document.getElementById("demo").innerHTML="我的第一个 JavaScript 函数";
    }
</script>
</head>
<body>
    <h1>我的 Web 页面</h1>
    <p id="demo">一个段落</p>
    <button type="button" onclick="myFunction()">尝试一下</button>
</body>
</html>
```

```html
<!DOCTYPE html>
<html>
<body>
    <h1>我的 Web 页面</h1>
    <p id="demo">一个段落</p>
    <button type="button" onclick="myFunction()">尝试一下</button>
    <script>
        function myFunction(){
            document.getElementById("demo").innerHTML="我的第一个 JavaScript 函数";
        }
    </script>
</body>
</html>
```

### 1.7.3、外部引入JavaScript

也可以把脚本保存到外部文件中。外部文件通常包含被多个网页使用的代码。

外部 JavaScript 文件的文件扩展名是 .js。

如需使用外部文件，请在 ```<script>```标签的 "src" 属性中设置该 .js 文件：

```html
<!DOCTYPE html>
<html>
<body>
	<script src="myScript.js"></script>
</body>
</html>
```

如果把JS源代码直接写在某个具体的页面上时(通常放在```<head>```标签下)，这样的成为内部的JavaScript。

但是当JS 代码越来越庞大的时候，我们最好把它独立另存为一个JS文件，扩展名为.js，然后在页面上引入即可，这样的称为外部的JS文件，它具有维护性高、可缓存(加载一次，无需加载)、方便未来扩展、复用性高等特点。

**注：引用外部js文件的script标签中不可以写JavaScript代码**

## 1.8、扩展知识点

**document.write() 的常用操作:**

​	除了直接输出文字外，它还支持带有HTML标签的输出内容。
​	比如直接输出一个标题
​	比如在输出内容中加入br换行标签
​	比如输入一张图片
​	......等等

```html
<!DOCTYPE html>
<html>
<body>

<h1>我的第一个 Web 页面</h1>

<p>我的第一个段落。</p>

<script>
    document.write("<h1>我是H1的内容</h1>");
</script>

</body>
</html>
```

请使用 document.write() 仅仅向文档输出写内容。

**如果在文档已完成加载后执行 document.write，整个 HTML 页面将被覆盖。**

```html
<!DOCTYPE html>
<html>
<body>

<h1>我的第一个 Web 页面</h1>

<p>我的第一个段落。</p>

<button onclick="myFunction()">点我</button>

<script>
function myFunction() {
    document.write(Date());
}
</script>

</body>
</html>
```

**alert()方法:**

​	alert()方法会弹出警告框。
​	可以添加多个alert();他们会按照顺序依次执行。

```html
<!DOCTYPE html>
<html>
<body>

<h1>我的第一个页面</h1>
<p>我的第一个段落。</p>

<script>
	window.alert(5 + 6);
</script>

</body>
</html>
```

**console.log():** 

写入到浏览器的控制台

如果您的浏览器支持调试，你可以使用 **console.log()** 方法在浏览器中显示 JavaScript 值。

浏览器中使用 F12 来启用调试模式， 在调试窗口中点击 "Console" 菜单。

```html
<!DOCTYPE html>
<html>
<body>

<h1>我的第一个 Web 页面</h1>

<script>
	a = 5;
	b = 6;
	c = a + b;
	console.log(c);
</script>

</body>
</html>
```

**innerHTML:** 

写入内容到 HTML 元素

```html
<!DOCTYPE html>
<html>
<body>

<h1>我的第一个 Web 页面</h1>

<p id="demo">我的第一个段落</p>

<script>
    //需从 JavaScript 访问某个 HTML 元素，您可以使用 document.getElementById(id) 方法。
	document.getElementById("demo").innerHTML = "段落已修改。";
    //document.getElementById("demo") 是使用 id 属性来查找 HTML 元素的 JavaScript 代码 。
	//innerHTML = "段落已修改。" 是用于修改元素的 HTML 内容(innerHTML)的 JavaScript 代码。
</script>

</body>
</html>
```

**click事件的基本用法:**

​	click事件是最常用的事件之一，所谓事件可以简单理解为用户的操作。
​	为了方便之后的学习，你应该先掌握着个简单事件的基本用法。

## 1.9、JavaScript注释及注意事项

单行注释:

```js
// 单行注释内容
var name = 'hm';
```

多行注释:

```js
/* 多行注释内容 */
/*
	var age = 18;
	var name = 'zs';
	console.log(name, age);
*/	
```

文档注释

```js
/**  文档注释内容 */
```

**注意事项：**

1、字母的大小写，Name和name是两个不同的标识符。

2、空格和换行。这一点和CSS代码规则类似:多余的空格会被忽略，可以将一行代码分成多行写。

3、分号作为一个语句的结束标志，分号之后是新语句的开始。虽然省略不写通常也是没有问题的，但还是建议大家写上。

<a id="p1-2"></a>
# 二、JavaScript变量和数据类型

## 2.1、标识符

所谓标识符，就是指变量、函数、属性的名字，或者函数的参数（凡是可以自己起名字的地方，都叫标识符）。

**标识符命名规范(包括函数名，变量等):**

- 由字母、数字、下划线、$符号组成;
- 不能以数字开头
- 命名不能是系统的关键字或保留字：比如new ，if，class......；关键字:赋予特殊含义的单词
- 区分大小写
- 命名最好用有意义的名称(见名之意)。比如说name，people......
- 驼峰原则: 首字母小写，多个单词组成，从第二个单词的首字母开始都大写; 比如: getNameById();
- 常量命名: 全部大写，多个单词组成，每个单词之间由下划线分割;APPLICATION_NAME

需要注意的是ECMAScript 中的一切，包括变量、函数名和操作符(typeof、instanceof、void等)都是严格区分大小写的。例如：text 和Text 表示两种不同的变量。

下面哪些变量名不合法?

```js
a	    
1
age18
18age
name
$name
_sex
&sex
theworld  theWorld
```

## 2.2、变量

![1572784109255](images01_base/1572784109255.png)

**1、什么是变量?**

​	可以发生改变的量就是变量，变量可以看做是存储数据的容器。比如一个瓶子，它既可以装入酱油、醋；也可以装入茅台和二锅头......。

​	变量是计算机内存中存储数据的标识符，根据变量名称可以获取到内存中存储的数据

​	**使用变量可以方便的获取或者修改内存中的数据。**

**2、变量的命名:**
​	可以给变量起一个简短名称，这个名称就是变量名。比如 x，或者更有描述性的名称，比如 age、name等。变量名对大小写敏感（y 和 Y 是两个不同的变量）且必须以字母或下划线开始。可以通过其名称来引用一个变量，以此显示或改变它的值。

**3、变量的声明:**
​      在 JavaScript 中创建变量通常称为“声明”变量，使用**关键字 var来声明变量**。

​      向变量赋值，使用等号;可以在声明变量时对其赋值，也可以先声明后赋值。

​      可以在一条语句中声明很多变量。该语句以 var 开头，并使用逗号分隔变量即可

> 分号用于分隔 JavaScript 语句。通常我们在每条可执行的语句结尾添加分号。使用分号的另一用处是在一行中编写多条语句。在 JavaScript 中，用分号来结束语句是可选的。

```js
// 声明一个变量count：
var count;

// 声明一个变量username：
var username;
```

在以上声明之后，变量并没有值，仅仅只是变量声明，不过可以在声明它们时向变量赋值，”=”是赋值符号，变量名在赋值符号符号的左边，而需要向变量赋的值在赋值符号的右侧。

```js
// 变量声明并赋值
var count = 5; 

var username= "Volvo";  
```

也可以先声明后赋值。

```js
// 先声明后赋值
var count ;      
count=100;

var username;      
username = “zhangsan”;
```

注释：在为变量赋文本值时，请为该值加引号（单引号或双引号都可以）。

如果所赋值的变量还未进行过声明，该变量会自动声明。

```js
// 这些语句：
x = 5; carname = "Volvo";

// 与这些语句的效果相同：
var x = 5; var carname = "Volvo";
```

如果再次声明了 JavaScript 变量，该变量也不会丢失其原始值。

```js
var x = 5; 

var x; // 5
```

在以上语句执行后，变量 x 的值仍然是 5。在重新声明该变量时，x 的值不会被重置或清除。
但是如果是在下面这种情况下，JavaScript 变量的值会改变

```js
var x = 5; 

var x = 7;
```

此时页面输出的值为7。

JavaScript也允许一次定义多个变量：

```js
var a，b，v;
```

还可以在定义变量的同时给变量赋初始值：

```js
var a=12，b，c=34;
```

如果一个变量没有赋值，它的值是undefined(未定义)。

**温馨提示：**
​	在一个HTML文档使用script标签嵌入多个JS语句的时候，这几个语句之间是相通的，或者说是有关联的。

**4、变量在内存中的存储**

```js
var name = "zhangsan";
var age = 18;
```

![](images01_base/微信截图_20200703170056.png)

**5、变量的简单使用:**

1、小明今年20岁，小胡比小明大15岁，请问小胡今年多大?

```js
<script>
    //1、声明一个变量,用来存储小明的年龄
    var xiaoming_age = 20;
    //2、声明一个变量,用来存储小胡的年龄
    var xiaohu_age;
    //3、通过小明的年龄运算给小胡赋值
    xiaohu_age = xiaoming_age + 15;
    //4、输出小胡的名字
    alert("小胡的年龄是:"+xiaohu_age);
</script>
```

2、在淘宝网购物，一件衣服55.4元，如果买4件衣服，共花多少钱?

```js
<script>
    //1、声明一个变量,用来存储衣服单价
    var price = 55.4;
    //2、声明一个变量,用来存储衣服的数量
    var count = 4;
    //3、计算得出总价格,并使用变量存储总价格
    var money = price * count;
    alert("衣服的总价格是:"+money);
</script>
```

3、思维题

​	交换两个变量的值

​	不使用临时变量，交换两个数值变量的值

```js
var n1 = 5;
var n2 = 6;

n1 = n1 + n2;   // 5 + 6 = 11
n2 = n1 - n2;   // 11 - 6 = 5;
n1 = n1 - n2;   // 11 - 5 = 6;
console.log(n1, n2);
```

## 2.3、关键字、保留字

ECMA-262 描述了一组具有特定用途的关键字。这些关键字可用于表示控制语句的开始或结束，或者用于执行特定操作等。按照规则，关键字也是语言保留的，不能用作标识符。以下就是ECMAScript的全部关键字。

**关键字:**

| break     | do       | instanceof | typeof |
| --------- | -------- | ---------- | ------ |
| case      | else     | new        | var    |
| catch     | finally  | return     | void   |
| continue  | for      | switch     | while  |
| debugger | function | this       | with   |
| default   | if       | throw      | delete |
| in        | try      |            |        |

**保留字:**

ECMA-262 还描述了另外一组不能用作标识符的保留字。尽管保留字在这门语言中还没有任何特定的用途。但它们有可能在将来被用作关键字。

| abstract | enum       | int       | short        |
| -------- | ---------- | --------- | ------------ |
| boolean  | export     | interface | static       |
| byte     | extends    | long      | super        |
| char     | final      | native    | synchronized |
| class    | float      | package   | throws       |
| const    | goto       | private   | transient    |
| debugger | implements | protected | volatile     |
| double   | import     | public    |              |

## 2.4、数据类型

Javascript脚本语言同其他语言一样，有它自身的基本数据类型，表达式和算术运算符及程序的基本程序框架。

Javascript提供了五种原始的数据类型和两种特殊数据类型用来处理数据和文字。

而变量提供存放信息的地方，表达式则可以完成较复杂的信息处理。

**原始数据(基本数据)类型:**

![1572787664843](images01_base/1572787664843.png)

**对象(复杂数据)类型:**

![1572787695679](images01_base/1572787695679.png)

> JavaScript数据类型分为以下几种:
>
> 字符串（String）、
>
> 数值(Number)、
>
> 布尔(Boolean)、
>
> 数组(Array)、
>
> 对象(Object)、
>
> 空（Null）、
>
> 未定义（Undefined）、
>
> 函数

JavaScript 拥有动态类型。这意味着相同的变量可用作不同的类型：

```js
var x;               // x 为 undefined
var x = 5;           // 现在 x 为数字
var x = "John";      // 现在 x 为字符串
```

### 2.4.1、字符串（String）

​	字符串是存储字符（比如 "Bill Gates"）的变量。

​	**字符串可以是引号中的任意文本。您可以使用单引号或双引号**;

​	变量字符串：如：var text="HTML5视频教程"

​	可以使用"+"进行字符串的连接。

​	**注:字符串类型可以和任何类型做+运算**;

- 字符串字面量

```js
'程序猿','程序媛',"JavaScript"
```

- 转义符

思考：如何打印以下字符串。

```js
我是一个"正直"的人 

我很喜欢"程序员'大牛'"
```

在 JavaScript 中，字符串使用单引号或者双引号来起始或者结束。那么如何输出单引号或者双引号呢？就要用到转义字符。

JavaScript中常用的转义字符：

![](images01_base/1498289626813.png)

- 字符串长度

  length属性用来获取字符串的长度

  ```javascript
  var str = 'Hello World';
  console.log(str.length);
  ```

- 字符串拼接

  字符串拼接使用 + 连接

  ```javascript
  console.log(11 + 11);
  console.log('hello' + ' world');
  console.log('100' + '100');
  console.log('11' + 11);
  console.log('male:' + true);
  ```

  1. 两边只要有一个是字符串，那么+就是字符串拼接功能
  2. 两边如果都是数字，那么就是算术功能。

### 2.4.2、数值（Number）

​	JavaScript 只有一种数值类型。

​	数值可以带小数点，也可以不带。

​	极大或极小的数字可以通过科学（指数）计数法来书写：3e4

​	数值可以通过运算符进行计算。

​	浮点数值的最高精度是16位小数，但是在进行算术计算时其精度远远不如整数。例如，0.1加0.2的结果不是0.3， 而是0.30000000000000004。这个舍入误差会导致无法测试特定的浮点数值。

​	数字可以写成十进制、八进制、十六进制。

​	八进制在js中表示是第一位一定要是0，后面就是八进制字数序列（0~7）

​	十六进制字面量前两位必须是0x，后面跟十六进制数字（0~9及A~F）。字母A~F不区分大小写。

 **温馨提示：**

​	科学（指数）计数法、八进制、十六进制表示的数字在输出时统统会转换成十进制。

- 数值字面量：数值的固定值的表示法

```js
110 1024  60.5
```

- 进制

```js
// 十进制
	var num = 9;
	进行算数计算时，八进制和十六进制表示的数值最终都将被转换成十进制数值。
    
// 十六进制
	var num = 0xA;
	数字序列范围：0~9以及A~F

// 八进制
    var num1 = 07;   // 对应十进制的7
    var num2 = 017;  // 对应十进制的15
    var num3 = 08;   // 对应十进制的8
    //数字序列范围：0~7
    //如果字面值中的数值超出了范围，那么前导零将被忽略，后面的数值将被当作十进制数值解析
```

- 浮点数
  - 浮点数的精度问题

```js
// 浮点数
	var a = 10.2;
	var b = 20.3333;
	var n = 5e-324;   // 科学计数法  5乘以10的-324次方  

// 浮点数值的最高精度是 17 位小数，但在进行算术计算时其精确度远远不如整数
   var result = 0.1 + 0.2;    // 结果不是 0.3，而是：0.30000000000000004
   console.log(0.07 * 100);
```

- 数值范围

```js
最小值：Number.MIN_VALUE，这个值为： 5e-324

最大值：Number.MAX_VALUE，这个值为： 1.7976931348623157e+308

无穷大(正无穷)：Infinity

无穷小（负无穷）：-Infinity
```

- 数值判断

```js
NaN：not a number
	NaN 与任何值都不相等，包括他本身
	
isNaN: is not a number
```

### 2.4.3、布尔（Boolean）

​	布尔（逻辑）只能有两个值：true 或 false。

​	**计算机内部存储：true为1，false为0**

### 2.4.4、数组（Array）

#### 2.4.4.1、为什么需要数组?

​	之前学习的数据类型，只能存储一个值(比如：Number/String。我们想存储班级中所有学生的姓名，此时该如何存储？

#### 2.4.4.2、数组的概念

​	所谓数组，就是将多个元素（通常是同一类型）按一定顺序排列放到一个集合中，那么这个集合我们就称之为数组。

#### 2.4.4.3、数组的定义及使用

数组是一个有序的列表，可以在数组中存放任意的数据，并且数组的长度可以动态的调整。

使用关键字new创建或[]

创建数组的方式：
​	var 数组名=[数组值......值N];

​	var 数组名= new Array(值1......值N);

​	var 数组名= new Array();

可以通过数组的下标来访问数组的元素。

​	数组元素的顺序从0开始

​            数组名[0]=值;

​      ​      数组名[1]=值;
​      ​      .....

```js
/**
    JavaScript数组的创建方式:
        1. 构造函数创建
            var 数组名 = new Array();       -- 得到一个空数组
            var 数组名 = new Array(数组);   -- 创建指定长度的数组
            var 数组名 = new Array(值1，值2，值3...)   创建数组并赋予值

        2. 快捷创建
            var 数组名 = [];
            var 数组名 = [值1，值2，值3....];

    JavaScript数组的属性:
        length属性  用来获取数组的长度

    JavaScript数组的特点:
        JS数组可以存储任意数据类型
        JS数组自动扩容，不是固定长度
        
	注意事项:
        当JS变量只有声明没有赋值的时候，去调用，那么undefined
        当JS根本没有这个变量的时候，去调用，那么报错 arr is not defined
*/
var arr1 = new Array();
document.write("数组1的长度为:" + arr1.length + "<br>");

var arr2 = new Array(5);
document.write("数组2的长度为:" + arr2.length + "<br>");

//给数组存储数据: 通过下标来存储数据
//语法: 数组名[下标] = 值;
arr2[0] = 10;
arr2[1] = 20;
arr2[2] = 30;
arr2[3] = 40;
arr2[4] = 50;
arr2[10] = 100; 

//调用数组里面的值
//语法: 数组名[下标]
document.write("下标1的值是:" + arr2[1] + "<br>");
document.write("下标20的值是:" + arr2[20] + "<br>");
document.write("数组2的长度为:" + arr2.length + "<br>");

var arr3 = new Array(5,"Hello",true,44.22);
document.write("数组3的长度为:" + arr3.length + "<br>");

var arr4 = []; //创建一个空数组  类似于 new Array();
var arr5 = [1,3,5,7]; //创建数组并赋值
var arr6 = [7];
document.write("数组6的长度为:" + arr6.length + "<br>");

// 补充 :数组 的长度 可以动态改变
var scores = [];  // 空数组
console.log(scores.length);

// 清空数组
scores.length = 0;
console.log(scores);
```

#### 2.4.4.4、遍历数组

> 遍历：遍及所有，对数组的每一个元素都访问一次就叫遍历。

数组遍历的基本语法：

```javascript
for(var i = 0; i < arr.length; i++) {
	// 数组遍历的固定结构
}

// 获取数组中的每一项，并打印（遍历数组）
var names = ['zs', 'ls', 'ww', 'zl'];
for (var i = 0; i < names.length; i++) {
    console.log(names[i]);
}

//遍历数组  先打印最后一项    长度 - 1    长度 - 2
var names = ['zs', 'ls', 'ww', 'zl'];
for (var i = names.length - 1; i >= 0; i--) {
    console.log(names[i]);
}
```

#### 2.4.4.5、数组中新增元素

数组的赋值

```javascript
// 格式：数组名[下标/索引] = 值;
// 如果下标有对应的值，会把原来的值覆盖，如果下标不存在，会给数组新增一个元素。
var arr = ["red", "green", "blue"];
// 把red替换成了yellow
arr[0] = "yellow";
// 给数组新增加了一个pink的值
arr[3] = "pink";
```

### 2.4.5、对象类型（Object）

​      对象由花括号定义。对象有属性和方法组成

​      在括号内部，无论是对象的属性还是方法都是以键和值对的形式 (key: value) 来定义。

​      多个属性或方法由逗号分隔

例如:

```javascript
var person1 = {
    id:1001，
    name:"张三"，
    age:12，
    eat:function(){
        alert("吃饭的行为");
    }，
    sleep:function(){
        alert("睡觉的行为");
    }
}
```

​      在Javascript中，所有的对象都继承自Object对象。

​      对象没有赋值的属性，该属性的值为undefined。

​      对象的方法是函数，后面会详解;

对象属性有两种寻址方式：

```js
对象名.属性名

对象名["属性名"]
```

你可以使用以下语法访问对象方法：

```js
objectName.methodName()
```

### 2.4.6、空（Null）

​	Null也是一个只有一个值的数据类型，它的值就是null，任何变量只要给其赋值为null的话这个变量的数据类型就是Null类型。

​	**可以通过将变量的值设置为 null 来清空变量**。

### 2.4.7、未定义（Undefined）

​	这个值表示变量不含有值或未声明。

​	这是一个很有意思的数据类型，因为它的值只有一个，那就是undefined。

​	在声明变量时如果没有将变量赋值的话这个变量也是属于Undefined类型的。

​	如果一个变量没有声明就直接去访问解释器会报错误信息，但是这样的变量如果使用typeof返回的结果也是"undefined"。

**Null和Undefined的区别：**

​	Null 已定义，并初始化为null;

​	Undefined:未定义，或者未初始化 。

## 2.5、typeof运算符

![1572785570614](images01_base/1572785570614.png)

typeof运算符可以查询数据类型:

其返回可能值有:undefined，boolean，number，string、object以及function.

可以使用typeof(变量名)查询数据类型

```js
var age = 18;

console.log(typeof age);  // 'number'

console.log(typeof(age)); 
```

## 2.6、数据类型转换

### 转换成字符串类型

- toString()

  ```js
  var str = "Hello World";
  var num = 120.2;
  var n = null;
  var un; 
  var bl = true;
  var arr = [1,2,3,5];
  var obj = {name:"张三"};
  function fn1(){}
  
  // 把数值转换为字符串类型
  console.log(typeof num.toString())
  
  // 把空类型转换为字符串类型
  // Cannot read property 'toString' of null  空类型没有这个方法
  // console.log(typeof n.toString());
  
  // 把未定义类型转换为字符串类型
  // Cannot read property 'toString' of undefined  未定义类型没有这个方法
  // console.log(un.toString())
  
  // 把布尔、数组、对象、函数转换为字符串类型
  console.log(typeof bl.toString());
  console.log(typeof arr.toString());
  console.log(typeof String(obj));
  console.log(typeof fn1.toString()); //通过这行代码,我们可以得出结论: 函数也是对象
  ```

- String()

  ```js
  String()函数存在的意义：有些值没有toString()，这个时候可以使用String()。比如：undefined和null
  var num = 18;
  var isRight = true;
  console.log(String(num));
  console.log(String(isRight));
  
  var a = null;
  console.log(typeof String(a));
  ```

- 拼接字符串方式

  num  +  ""，当 + 两边一个操作符是字符串类型，一个操作符是其它类型的时候，会先把其它类型转换成字符串再进行字符串拼接，返回字符串

### 转换成数值类型

- Number()

  ```js
  // Number()可以把任意值转换成数值，如果要转换的字符串中有一个不是数值的字符，返回NaN
  
  // 1 Number()
  var str = 'abc';   //   Number(str)   -》 NaN
  var isRight = true;  //  Number(isRight) -> 1
  
  console.log(Number(str)); //NaN
  console.log(Number(isRight)); //1
  
  console.log(Number('123')); //123
  // Number() 把字符串转换成数值类型的时候，如果字符串中有一个字符不是数字，返回NaN
  console.log(Number('123abc')); //NaN
  ```

- parseInt()

  ```js
  var str = '123';
  var isRight = false;
  
  console.log(parseInt(str)); //123
  // parseInt 无法把布尔类型转换成数值类型 返回的结果是NaN
  console.log(parseInt(isRight)); //NaN
  
  
  //var s1 = 'abc';   //  parseInt(s1) -> NaN
  var s1 = '123abc';
  // parseInt 在转换字符串的时候，如果遇到数字就会转换数字，如果遇到非数字就会返回
  console.log(parseInt(s1)); //123
  
  var s2 = 'abc123'; // 如果字符串中第一个字符是非数字 此时返回NaN
  console.log(parseInt(s2)); //NaN
  ```

- parseFloat()

  ```js
  var str = '123.67';
  var isRight = true;
  console.log(parseFloat(str)); //123.67
  console.log(parseInt(str)); // 123
  console.log(parseFloat(isRight)); // parseFloat 无法转换布尔类型  返回的是NaN
  
  var str = '123.12abc';
  console.log(parseFloat(str)); //123.12
  
  var str = '123abc';
  console.log(parseFloat(str)); //123
  
  parseFloat()把字符串转换成浮点数
  parseFloat()和parseInt非常相似，不同之处在与parseFloat()可以得到浮点值
  ```

- +，-0等运算

  ```javascript
  var str = '500';
  console.log(+str);		// 取正
  console.log(-str);		// 取负
  console.log(str - 0);
  ```

### 转换成布尔类型

- Boolean()

  将各种类型的值转化成Boolean类型的规则如下：

​		Number:任意非0的数值为true，0值和NaN为"false"。

​		String:所有的非空字符串转化为 true;""（空字符串）转化成false

​		Object的任何非空对象都会转化为 true;

​		在javascript中，只要逻辑表达式不返回undefined不返回null，就都是真的。

​	注:通常和流程控制语句结合使用

​	0  ''(空字符串) null undefined NaN 会转换成false  其它都会转换成true

```js
var str1 = "Hello World";
var str2 = "";
var num = 120.2;
var n = null;
var un; 
var bl = true;
var arr = [];
var obj = {};
// function fn1(){}

// 任何非空字符串都转换为true,空字符串转换为false
console.log(Boolean(str1)); // true
console.log(Boolean(str2)); // false

// 任何非0数值都转换为true,0和NaN转换为false
console.log(Boolean(num)); // true
console.log(Boolean(0)); // false
console.log(Boolean(NaN)); // false

// 对象和数组都转换为true
console.log(Boolean(arr));
console.log(Boolean(obj));

// Null和Undefined都转换为false
console.log(Boolean(n));
console.log(Boolean(un));
```

<a id="p1-3"></a>
# 三、JavaScript运算符和表达式

## 3.1、基本概念

JavaScript描述了一组用于操作数据值的运算符，包括一元运算符(++ --)、逻辑运算符、算术运算符、关系运算符、三目运算符及赋值运算符。ECMAScript 中的运算符适用于很多值，包括字符串、数值、布尔值、对象等。

​	**表达式：**

​		表达式由一个或多个操作数通过操作符组合而成，就是由数据和运算符组成的一个式子。

​		例如：x+y；x/10; x+23/2+y; x%y等都是表达式。
​	**操作数：**

​		表达式中的变量成为操作数；

​	**运算符：**

​		表达式中起运算作用的符号称为运算符；

​	简而言之:用来做运算的符号就是运算符;由运算符连接起来的式子叫表达式;

## 3.2、算数运算符

算术运算符即算术运算符号。是完成基本的算术运算 (arithmetic operators) 符号，就是用来处理四则运算的符号。

算数运算符分为以下:

![1572788268226](images01_base/1572788268226.png)

**加法运算符（+）:**

```javascript
var box = 1 + 2; //等于3
var box = 1 + NaN; //NaN，只要有一个NaN 就为NaN
var box = Infinity + Infinity; //Infinity
var box = -Infinity + -Infinity; //-Infinity
var box = Infinity + -Infinity; //NaN，正无穷和负无穷相加等NaN
var box = 100 + '100';//100100，字符串连接符，有字符串就不是加法
var box = '您的年龄是：' + 10 + 20; //您的年龄是：1020，被转换成字符串
var box = 10 + 20 + '是您的年龄'; //30 是您的年龄，没有被转成字符串
var box = '您的年龄是：' + (10 + 20); //您的年龄是：30，没有被转成字符串
其中NaN是not a number的缩写，表示不是一个数；infinity是无穷大的数。
任意数据类型的数值和字符串做 “+”运算，得到的肯定是字符串。
```

**减法运算符:**

```javascript
var box = 100 - 70; //等于30
var box = -100 - 70 ;//等于-170
var box = -100 - -70; //-30，一般写成-100 - (-70)比较清晰
var box = 1 - NaN; //NaN，只要有一个NaN 就为NaN
var box = Infinity - Infinity; //NaN
var box = -Infinity - -Infinity;//NaN
var box = 100 - true; //99，true 转成数值为1
var box = 100 -false;  //100，false转成数值为0
var box = 100 - '';  //100，''转成了0
var box = 100 - '70';  //30，'70'转成了数值70
var box = 100 - null;  //100，null 转成了0
var box = 100 - 'Lee';  //NaN，Lee 转成了NaN
```

**乘法运算符:**

```js
var box = 100 * 70;  //7000
var box = 100 * NaN;  //NaN，只要有一个NaN 即为NaN
var box = Infinity * Infinity;  //Infinity
var box = -Infinity * Infinity ;  //-Infinity
var box = -Infinity * -Infinity ;  //Infinity
var box = 100 * true;  //100，true 转成数值为1
var box = 100 * '';  //0，''转成了0
var box = 100 * null;  //0，null 转成了0
var box = 100 * 'Lee';  //NaN，Lee 转成了NaN
```

**除法运算符:**

```js
var box = 100 / 70;  //1.42....
var box = 100 / NaN;  //NaN
var box = Infinity / Infinity;  //NaN
var box = -Infinity / Infinity ;  //NaN
var box = -Infinity / -Infinity;  //NaN
var box = 100 / true;  //100，true 转成1
var box = 100 / '';  //Infinity，
var box = 100 / null;  //Infinity，
var box = 100 / 'Lee';  //NaN
```

**求模运算符（求余数）:**

```js
var box = 10 % 3;  //1，余数为1
var box = 100 % NaN;  //NaN
var box = Infinity % Infinity;  //NaN
var box = -Infinity % Infinity ;  //NaN
var box = -Infinity % -Infinity;  //NaN
var box = 100 % true;  //0
var box = 100 % '';  //NaN
var box = 100 % null;  //NaN
var box = 100 % 'Lee';  //NaN
```

JS里面的算数运算规则:

​	1、任意数据类型和字符串进行加法运算,都是字符串的拼接

​	2、任意数据类型和NaN进行四则运算,结果都是NaN

​	3、当true和false参与运算,true转换为1,false转换为0

​	4、除+运算外,数值类型字符串参与运算,都转换为数值;但是非数值类型字符参与运算,结果都是NaN

​	5、除+运算外,空字符串转换为0,null转换为0

​	6、0可以作为除数,得到结果都是无穷大

​	7、0参与取余运算,得到结果都是NaN

## 3.3、一元运算符

​	只能操作一个值的运算符叫做一元运算符。严格来说，一元运算符是属于算术运算符的;

​	一元运算符：++ --:使数值递增/递减1

- 前置++

```js
var num1 = 5;
++ num1;  // num1 = 6;

var num2 = 6;
console.log(num1 + ++ num2); // 13
```

- 后置++

```js
var num1 = 5;
num1 ++;   // num1 = 6

var num2 = 6 
console.log(num1 + num2 ++); // 12
```

- Why?

```js
var a = 1; var b = ++a + ++a; console.log(b);//5    
var a = 1; var b = a++ + ++a; console.log(b);//4    
var a = 1; var b = a++ + a++; console.log(b);//3    
var a = 1; var b = ++a + a++; console.log(b);//4  
```

**前置和后置的区别:**

​      在没有赋值操作，前置和后置是一样的。但在赋值操作时，如果递增或递减运算符前置，那么前置的运算符会先累加或累减再赋值，如果是后置运算符则先赋值再累加或累减。运算的时候也是一样;

​      其他类型应用一元运算符的规则

```js
var box = '89'; box++; //90，数值字符串自动转换成数值
var box = 'ab'; box++; //NaN，字符串包含非数值转成NaN
var box = false; box++; //1，false 转成数值是0，累加就是1
var box = 2.3; box++; //3.3，直接加1
```

注：如果数值字符串使用一元运算符,即使是加法运算,也直接转换为数值;

## 3.4、赋值运算符

赋值运算符用于给 JavaScript 变量赋值。

```js
=        赋值
+=       x+=y      等价于 x=x+y
-=       x-=y      等价于 x=x-y
*=       x*=y      等价于 x=x*y
/=       x/=y      等价于 x=x/y
%=       x%=y      等价于 x=x%y
```

​	在JavaScript中，赋值运算符是“=”，其含义就是把赋值运算符的右边的数值或表达式的值赋给赋值运算符的左边的变量或表达式。

```js
例如：
	var t=5;其意义就是把数值5赋给变量t;
	var k=x+y+5;其意义就是把表达式x+y+5最后的值赋给变量k。
	var box = 100；
	box += 100; //200，+=代替box+100
```

## 3.5、关系运算符(比较运算符)

比较运算符是比较两个数的大小的运算符，返回的是一个布尔值。

用于进行比较的运算符称作为关系运算符：小于(<)、大于(>)、小于等于(<=)、大于等于(>=)、相等(==)、不等(!=)、全等(恒等)(===)、不全等(不恒等)(!==)

**比较原则:**

```js
1、若一个是数值字符串，一个是数值，字符串会自动转换成数值进行比较。
	var box = '3' > 22; //false      var box = '3' > '22'; //true
	var box = 'a' > 'b'; //false  a=97，b=98; var box = 'a' > 'B'; //true  B=66
2、若两个都是数值字符串，则比较首个数字的大小。
3、布尔值的false和true会转换成0和1
4、两个操作数都是数值，则数值比较；
5、两个操作数都是字符串，则比较两个字符串对应的字符编码值；
	字符转ascii码：用charCodeAt();
	var x = "我";      var y = "你";       alert(x>y); //true
```

**在相等和不等的比较上，如果操作数是非数值，则遵循一下规则：**

```js
1.一个操作数是布尔值，则比较之前将其转换为数值，false 转成0，true 转成1；
2.一个操作数是字符串，则比较之前将其转成为数值再比较；
3.不需要任何转换的情况下，null 和undefined 是相等的；
4.一个操作数是NaN，则==返回false，!=返回true；并且NaN 和自身不等；
5.在全等和全不等的判断上，比如值和类型都相等，才返回true，否则返回false。
```

**特殊值对比表:**

```js
表达式                        值
null == undefined      		true
'NaN' == NaN            	false
5 == NaN                    false
NaN == NaN               	false
false == 0                  true
true == 1                   true
true == 2                   false
undefined == 0            	false
null == 0                   false
'100' == 100                true
'100' === 100               false
```

相等运算符 == ：判断两个操作数是否相等。不同的数据类型会自动转换为相等的数据类型再做比较。

等同运算符=== ：全等（值和类型），严格意义的相等，两个操作数的值和他们的类型必须完全一致。

```js
var result = '55' == 55;  	// true
var result = '55' === 55; 	// false 值相等，类型不相等
var result = 55 === 55; 	// true
```

## 3.6、逻辑运算符

逻辑运算符通常用于布尔值的操作，一般和关系运算符配合使用，有三个逻辑运算符：

逻辑与(AND)、逻辑或(OR)、逻辑非(NOT)。

```js
&& 与 两个操作数同时为true，结果为true，否则都是false

|| 或 两个操作数有一个为true，结果为true，否则为false

!  非  取反
```

- 逻辑与运算符属于短路操作，顾名思义，如果第一个操作数返回是false，第二个数不管是true 还是false 都返回的false。
- 和逻辑与运算符相似，逻辑或运算符也是短路操作。当第一操作数的求值结果为true，就不会对第二个操作数求值了。
- 逻辑非运算符可以用于任何值。无论这个值是什么数据类型，这个运算符都会返回一个布尔值。它的流程是：先将这个值转换成布尔值，然后取反。

注: JavaScript虽说也有& 和 |，但是这里不是做逻辑运算符，而是位运算符

## 3.7、三目运算符

​      三目运算符，又叫三元条件运算符

​      三元条件运算符其实就是后面将要学到的if 语句的简写形式。

​      根据条件在两个语句中执行其中的一个，使用符号 ？：

​      语法如下：
​      ​      条件表达式？语句1：语句2

​      参数说明：

​      ​      条件表达式，结果会被作为布尔值处理
​      ​      语句1：如果条件表达式返回true则执行
​      ​      语句2：如果条件表达式返回false则执行

```js
var box = 5 > 4 ? '对' : '错'; //对，5>4 返回true 则把'对'赋值给box，反之，把错赋给box。

// 判断一个年龄是否成年, 当年龄超过18 返回  成年  否则返回未成年
var age = 19;
// console.log( age >= 18 ? '成年' : '未成年' );

var msg = age >= 18 ? '成年' : '未成年';
console.log(msg);
```

## 3.8、运算符优先级

​      运算符优先级描述了在计算表达式时执行运算 的顺序。先执行具有较高优先级的运算，然后执行较低优先级的运算。例如，先执行相乘，再执行相加。

​      运算符比较多，可以合理使用()来改变表达式的优先级。

​      ()的用法和数学中的()用法相同，()内的会优先计算。

![1572788804081](images01_base/1572788804081.png)

<a id="p1-4"></a>
# 四、JavaScript流程控制语句

## 4.1、语句的定义

​	在ECMAScript 中，所有的代码都是由语句来构成的。

​	一行代码就是一条简单语句。形式上可以是单行语句，或者由一对大括号“｛｝”括起来的复合语句，复合语句包含若干条简单语句，它可以作为一个单行语句处理。复合语句也称为语句块。

​	单行语句:一行代码简单语句

​	复合语句:由一对大括号“｛｝”括起来的若干条简单语句，也叫语句块

## 4.2、流程控制语句分类

![1572789742180](images01_base/1572789742180.png)

任何复杂的程序逻辑都可以通过”顺序”、”条件(分支)”和”循环”三种基本的程序结构来实现。

​            顺序程序结构就是从上往下顺序执行语句；程序默认就是由上到下顺序执行的

​            条件(分支)程序结构就是根据不同的情况执行不同的语句；

​      ​      循环程序结构就是某些语句要循环执行多次。

1. 条件语句(分支语句)

  ​      if单分支语句

  ​      if-else双分支语句

  ​      if - else if多分支语句

  ​      switch开关语句

2. 循环语句

    for循环语句

    while循环语句

    do-while循环语句

    for／in循环语句 (增强for循环、foreach循环)

## 4.3、条件语句

if语句即条件判断语句，一共有三种格式：

​	单分支的条件语句；

​	双分支的条件语句

​	多分支的条件语句。

条件语句用于基于不同的条件来执行不同的动作。

### 4.3.1、单分支的条件语句

![1572789749454](images01_base/if.png)

if(){} 语句 - 只有当指定条件为 true 时，使用该语句来执行代码

```js
if (/* 条件表达式 */) {
  // 执行语句
}
```

**注意：**
​	（1） 放在if之后的括号里的返回值为boolean类型的表达式或boolean值，即这个表达式的返回值只能是true或false。

​	（2） 如果表达式的值为true，则执行语句；如果表达式的值为false，则什么也不执行。

​	（3） 花括号括起来的语句块可以只有一行语句，也可以由多行代码构成。一个语句块通常被当成一个整体来执行。 如果语句块只有一行语句时，则可以省略花括号，因为单行语句本身就是一个整体，无须花括号来把它们定义成一个整体。建议都加花括号;

### 4.3.2、双分支的条件语句

![1572789831282](images01_base/if2.png)

if()...else 语句 - 当条件为 true 时执行语句1，当条件为 false 时执行语句2

```js
if (/* 条件表达式 */){
  // 成立执行语句
} else {
  // 否则执行语句
}

if (条件表达式){
    语句1;
}else {
    语句2;
}
```

​	**注意：**
​	（1）放在if之后的括号里的返回值为boolean类型的表达式或boolean值，即这个表达式的返回值只能是true或false。

​	（2）如果if表达式的值为true，则执行语句1；如果表达式的值为false，则执行语句2。

### 4.3.3、多分支的if条件语句

![1572789854607](images01_base/if3.png)

​      if()...else if()....else 语句 - 使用该语句来选择多个代码块之一来执行.

```js
if (/* 条件1 */){
  // 成立执行语句
} else if (/* 条件2 */){
  // 成立执行语句
} else if (/* 条件3 */){
  // 成立执行语句
} else {
  // 最后默认执行语句
}
```

​      **语法：**

```js
if (条件表达式) {
    语句1;
} else if (条件表达式) {
   语句2;
} ...
else{
   语句n;
}
```

​	注:if语句()中的表达式会自动转换成布尔值。

​	满足条件即执行对应语句，然后语句就结束；如果都不满足，则执行else语句块；当然else语句块可以不存在

### 4.3.4、switch多条件选择语句

![1572789876543](images01_base/1572789876543.png)

​      switch语句又称开关语句，它与多重if语句类似，前者用于等值判断，后者用于区间值和等值判断。switch语句的作用是根据表达式的值，跳转到不同的语句。switch 语句用于基于不同的条件来执行不同的动作。

​      **语法：**

```js
switch (expression) {
  case 常量1:
    语句;
    break;
  case 常量2:
    语句;
    break;
  case 常量3:
    语句;
    break;
  …
  case 常量n:
    语句;
    break;
  default:
    语句;
    break;
}
```

**switch多条件选择语句:**

​	首先设置表达式，随后表达式的值会与结构中的每个case 的常量表达式做比较。如果存在匹配，则与该 case 关联的代码块会被执行。

​	使用 break 来阻止代码自动地向下一个 case 运行。default 关键词来规定匹配不存在时做的事情，也就是说，当没有匹配的值时，执行default下的语句。

​	**switch 语句在比较值时使用的是全等操作符, 因此不会发生类型转换**（例如，字符串'10' 不等于数值 10）

**工作原理：**
​	首先设置表达式 n（通常是一个变量）。

​	随后表达式的值会与结构中的每个 case 的值做比较。

​	如果存在匹配，则与该 case 关联的代码块会被执行。

​	请使用 break 来阻止代码自动地向下一个 case 运行。

​	default 关键词来规定匹配不存在时做的事情;相当于if里的else

> 注意:
> ​     1、每个case语句下的break语句一般不可以省略，break语句表示退出switch语句，如果省略，则会继续执行下一个case语句中的代码，直到遇到break语句跳出switch语句。
> ​     2、default语句可以出现在switch语句中任何地方，如果放在最后，其中的break语句可省略。default语句也可省略。
> ​     3、每个case语句没有先后顺序之分，但建议按照常量表达式的值从小到大的顺序。
> ​     4、switch语句用于等值判断，也就是说表达式的结果是个具体的值；而多重if选择结果的表达式的值是个区间，比如大于100而小于200。

**输入一个数字，打印对应的星期**

```js
var day = 10;
switch (day) {
    case 1:
        console.log('星期一');
        break;
    case 2:
        console.log('星期二');
        break;
    case 3:
        console.log('星期三');
        break;
    case 4:
        console.log('星期四');
        break;
    case 5:
        console.log('星期五');
        break;
    case 6:
        console.log('星期六');
        break;
    case 7:
        console.log('星期日');
        break;
    default:
        console.log('输入的值不在星期范围内');
        break;
}
```

### 4.3.5、条件语句练习

**案例：**
​	求两个数的最大数

```js
var num1 = 2;
var num2 = 5;

if (num1 > num2) {
    console.log('最大值是：' + num1);
} else {
    console.log('最大值是: ' + num2);
}
```

​	判断一个数是偶数还是奇数

```js
// 判断一个数是偶数还是奇数
var num = 5;
if (num % 2 === 0) {
    console.log('num是偶数');
} else {
    console.log('num是奇数');
}
```

​	分数转换，把百分制转换成ABCDE   <60  E  60-70 D  70-80 C  80-90 B  90 - 100 A

```js
// 分数转换，把百分制转换成ABCDE   <60  E  60-70 D  70-80 C  80-90 B  90 - 100 A
var score = 59;
if (score >= 90 && score <= 100) {
    console.log('A');
} else if (score >= 80 && score < 90) {
    console.log('B');
} else if (score >= 70 && score < 80) {
    console.log('C');
} else if (score >= 60 && score < 70) {
    console.log('D');
} else {
    console.log('E');
}

var score = 59;
if (score >= 90) {
    console.log('A');
} else if (score >= 80) {
    console.log('B');
} else if (score >= 70) {
    console.log('C');
} else if (score >= 60) {
    console.log('D');
} else {
    console.log('E');
}

var score = 6; 
score = parseInt(score / 10);
switch (score) {
    case 10:
    case 9:
        console.log('A');
        break;
    case 8:
        console.log('B');
        break;
    case 7:
        console.log('C');
        break;
    case 6:
        console.log('D');
        break;
    default: 
        console.log('E');
        break;
}
```

## 4.4、循环程序结构

​	如果希望一遍又一遍地运行相同的代码，那么使用循环是很方便的。比如在页面上输出100遍“我爱HTML5编程”，如果不用循环，document.write("我爱HTML5编程```<br/>```");要写100遍。如果用循环则代码这样写即可：

```js
for(var i=1;i<=100;i++){
	document.write("我爱HTML5编程<br/>");
}
```

循环程序的结构有三要素：循环的初始值、循环条件(循环的结束值)和循环的迭代，所谓循环的迭代就是如何从初始值到结束值，比如是每次加1还是每次加2，诸如此类等。当然，一个循环程序还有包含一个循环体。

### 4.4.1、while 语句

![1572789991861](images01_base/while.png)

​	while循环会在指定条件为真时循环执行代码块，它是一种先判断，后运行的循环语句，也就是说，必须满足条件了之后，方可运行循环体。用于不太确定循环次数的场合。

**语法：**

```js
// 当循环条件为true时，执行循环体，
// 当循环条件为false时，结束循环。
while (循环条件) {
  //循环体
}
```

代码示例：

```javascript
// 打印1-100之间所有的数字
var i = 1;
while (i <= 100) {
    console.log(i);
    // i = i + 1;
    // i += 1;
    i++;
}

// 计算1-100之间所有数的和
// 初始化变量
var i = 1;
var sum = 0;
// 判断条件
while (i <= 100) {
  // 循环体
  sum += i;
  // 自增
  i++;
}
console.log(sum);
```

**案例：**
​	打印100以内 7的倍数

```js
// 打印100以内 7的倍数
var i = 1;
while (i <= 100) {
    // 判断当前的i是否是7的倍数
    if (i % 7 === 0) {
        console.log(i);
    }
    // i自身+1
    i++;
}
```

​	打印100以内所有偶数

```js
// 打印100以内所有偶数
var i = 1;
while (i <= 100) {
    // 判断当前的i是否是偶数
    if (i % 2 === 0) {
        console.log(i);
    }
    // i自身+1
    i++;
}
```

​	打印100以内所有偶数的和

```js
// 打印100以内所有偶数的和
var i = 1;
var sum = 0;
while (i <= 100) {
    // 判断当前的i是否是偶数，如果是偶数的话累加
    if (i % 2 === 0) {
        sum += i;
    }
    // i自身+1
    i++;
}
console.log(sum);
```

案例1:循环输出从1开始的数值; 直到这个数值(n*2+8)/3 为20才结束循环

案例2:从弹出框循环输入字符串,直到输入的值为end才结束循环 

```js
var inputStr = prompt("请输入一个字符串"); 
```

### 4.4.2、do...while循环

![1572790046688](images01_base/dl.png)

​	do...while 循环是 while 循环的变体，在检查条件是否为真之前，该循环会至少执行一次do下的代码块(循环体)，然后如果条件为真的话，就会重复这个循环，否则退出该循环体。常用于至少执行一次循环体，再判断要不要继续循环的场合。

**语法：**

```js
do {
  // 循环体;
} while (循环条件);
```

代码示例：

```javascript
// 初始化变量
var i = 1;
var sum = 0;
do {
  sum += i;//循环体
  i++;//自增
} while (i <= 100);//循环条件
```

案例：

```js
// 求100以内所有3的倍数的和
var i = 1;
var sum = 0;
do {
    // 循环体
    // 判断是否是3的倍数，如果是3的倍数累加
    if (i % 3 === 0) {
        sum += i;
    }
    // i自身+1
    i++;
} while (i <= 100);
console.log(sum);
```

### 4.4.3、for语句

![1572790067885](images01_base/1572790067885.png)

while和do...while一般用来解决无法确认次数的循环。for循环一般在循环次数确定的时候比较方便

**语法：**

```js
// for循环的表达式之间用的是;号分隔的，千万不要写成,
for (初始化表达式1; 判断表达式2; 自增表达式3) {
  // 循环体4
}
```

​      语句1: 在循环体(代码块)开始前执行，也就是循环初始值。

​      语句2: 定义运行循环（代码块）的条件，语句2返回true，则循环再次开始，如果返回 false，则循环将结束

​      语句3: 在循环(代码块)已被执行之后执行，就是循环的迭代部分， 语句3有多种用法，增量可以是负数 (i--)，或者更大 (i=i+15)

**for循环执行机制:**

![1572790102033](images01_base/1572790102033.png)

执行顺序：1243  ----  243   -----243(直到循环条件变成false)

1. 初始化表达式
2. 判断表达式
3. 自增表达式
4. 循环体

### 4.4.4、for...in语句

​	for...in 语句用于遍历数组或者对象的属性（通常我们使用for/in 语句循环遍历对象的属性，在数组中可以遍历数组中的所有元素）。

​	for...in 循环中的代码每执行一次，就会对数组的元素或者对象的属性进行一次操作。

**for..in遍历数组**

```js
// 定义一个数组
var arr = [13,21,34,42,53,63];

// 普通for循环遍历
for(var i = 0;i < arr.length;i++){
    console.log(arr[i]);
}

// 使用for..in遍历数组
for(var i in arr){
    console.log(arr[i]);
}
```

**for..in遍历对象**

```js
// 创建一个对象
var person = {
    name : "jack",
    age : 12,
    height: 178
}

//列举对象属性名及其值
for(var pro in person){
    console.log(pro+" "+person[pro])
}
```

​      在JavaScript语言中，支持循环语句的相互嵌套，即在一个循环语句中嵌套另一个循环语句，也就是说，for循环语句可以嵌套for语句，也可以嵌套while循环语句，或者do..while循环语句，其他的循环语句也是一样的。

​      需要注意的是，break和continue语句用在循环嵌套中，这两条语句只对离它最近的循环语句有效。比如如果break语句用在内层的循环语句中，则只退出内层的循环，对外层循环没有影响。

### 4.4.5、循环语句练习

**案例：**

```js
打印1-100之间所有数
for (var i = 1; i <= 100; i++) {
    console.log(i);
}

var i = 1;
for (; i <= 100; ) {
	console.log(i);
	i++;
}

求1-100之间所有数的和
var sum = 0;
for (var i = 1; i <= 100; i++) {
    // sum = sum + i;
    sum += i;
}
console.log(sum);

求1-100之间所有数的平均值
var sum = 0;
var avg;
for (var i = 1; i <= 100; i++) {
    sum += i;
}
avg = sum / 100;
console.log(avg);

求1-100之间所有偶数的和
var sum = 0;
for (var i = 1; i <= 100; i++) {
    // 找到偶数
    if (i % 2 === 0) {
        sum += i;
    }
}
console.log(sum);

同时求1-100之间所有偶数和奇数的和
var oddSum = 0; // 奇数的和
var evenSum = 0; // 偶数的和
for (var i = 1; i <= 100; i++) {
    // 判断i是奇数还是偶数
    if (i % 2 === 0) {
        // 偶数
        evenSum += i;
    } else {
        //奇数
        oddSum += i;
    }
}
console.log('奇数的和：' + oddSum);
console.log('偶数的和：' + evenSum);

打印正方形
// 使用拼字符串的方法的原因
// console.log 输出重复内容的问题
// console.log 默认输出内容介绍后有换行
var start = '';
for (var i = 0; i < 10; i++) {
  for (var j = 0; j < 10; j++) {
    start += '* ';
  }
  start += '\n';
}
console.log(start);

打印直角三角形
var start = '';
for (var i = 0; i < 10; i++) {
  for (var j = i; j < 10; j++) {
    start += '* ';
  }
  start += '\n';
}
console.log(start);

打印9*9乘法表
var str = '';
for (var i = 1; i <= 9; i++) {
  for (var j = i; j <=9; j++) {
    str += i + ' * ' + j + ' = ' + i * j + '\t';
  }
  str += '\n';
}
console.log(str);
```

## 4.5、跳转语句

break:立即跳出整个循环，即循环结束，开始执行循环后面的内容（直接跳到大括号）

continue:立即跳出当前循环，继续下一次循环（跳到i++的地方）​      

continue 语句只能用在循环中；break能用在循环或 switch 中。

**案例：**

```javascript
求整数1～100的累加值，但要求碰到个位为3的数则停止累加
求整数1～100的累加值，但要求跳过所有个位为3的数
var sum = 0;
for (var i = 1; i <= 100; i++) {
    if (i % 10 === 3) {
        // 如果找到个位为3的数字 ，继续执行下一次循环
        continue;
    }
    sum += i;
}
console.log(sum);
```

## 4.6、调试

- 过去调试JavaScript的方式
  - alert()
  - console.log()
- 断点调试

> 断点调试是指自己在程序的某一行设置一个断点，调试时，程序运行到这一行就会停住，然后你可以一步一步往下调试，调试过程中可以看各个变量当前的值，出错的话，调试到出错的代码行即显示错误，停下。

- 调试步骤

```javascript
浏览器中按F12-->sources-->找到需要调试的文件-->在程序的某一行设置断点
```

- 调试中的相关操作

```javascript
Watch: 监视，通过watch可以监视变量的值的变化，非常的常用。
F10: 程序单步执行，让程序一行一行的执行，这个时候，观察watch中变量的值的变化。
F8：跳到下一个断点处，如果后面没有断点了，则程序执行结束。
```

tips: ***监视变量，不要监视表达式，因为监视了表达式，那么这个表达式也会执行。***

1. 代码调试的能力非常重要，只有学会了代码调试，才能学会自己解决bug的能力。初学者不要觉得调试代码麻烦就不去调试，知识点花点功夫肯定学的会，但是代码调试这个东西，自己不去练，永远都学不会。
2. 今天学的代码调试非常的简单，只要求同学们记住代码调试的这几个按钮的作用即可，后面还会学到很多的代码调试技巧。

## 4.7、代码规范

```js
1.命名规范	
	变量、函数 的命名 必须要有意义
	变量 的名称一般用名词
	函数 的名称一般用动词
2.变量规范   
	操作符的前后要有空格
	var name = 'zhangsan';	  5 + 6
3.注释规范
	// 这里是注释
4.空格规范
	if (true) {
      
	}
	for (var i = 0; i <= 100; i++) {
      
	}
5.换行规范
	var arr = [1, 2, 3, 4];
	if (a > b) {
      
	}
	for (var i = 0; i < 10; i++) {
      
	}
	function fn() {
      
	}
```

<a id="p1-5"></a>
# 课后习题

## part 1

```html
1、( )年设计出JavaScript。
    A、1992    B、1993    C、1994   D、1995
2、( )公司设计出JavaScript。
    A、微软   B、网景    C、谷歌   D、苹果
3、JavaScipt是一门( )语言。
    A、脚本   B、非脚本   C、运行在服务端  D、浏览器不能运行
4、JavaScipt是一门( )类型语言。
    A、弱   B、强   C、运行在服务端  D、浏览器不能运行
5、JavaScipt是一门( )语言。
    A、强  B、运行在客户端  C、运行在服务端  D、浏览器不能运行
6、JavaScipt是一门( )语言。
    A、解释型   B、编译型  C、解释编译型  D、编译解释型
7、JavaScipt的特点()。
    A、简单性  B、安全性 C、动态性  D、跨平台性
8、JavaScipt对用户的响应采用()。
    A、事件驱动  B、命令驱动  C、代码驱动  D、请求驱动
9、JavaScipt可用于()设备。
    A、PC    B、手机   C、笔记本电脑  D、平板电脑
10、JavaScipt由()构成。
    A、DOM   B、BOM   C、ECMAScript D、JScript
11、()描述了JavaScript的基本语法。  
    A、DOM   B、BOM   C、ECMAScript D、JScript
12、JavaScript中的()主要处理浏览器窗口的方法和接口。
    A、DOM   B、BOM   C、ECMAScript D、JScript
13、 JavaScript中的()主要处理网页内容的方法和接口。
    A、DOM   B、BOM   C、ECMAScript D、JScript
14、如果要删除网页中的一个<span>标签，需要JavaScript中的()方法和接口。
    A、DOM   B、BOM   C、ECMAScript D、JScript
```

## part 2

```html
1、<script>通常放在()标签中。
    A、<body>    B、<head>    C、<header>    D、<foot>
2、<script>引用外部文件时，以下说法正确的是()。
    A、<script>和</script>必须成对出现。
    B、不可以在<script>标签中写代码
    C、引用外部的JS文件，使用<script>的标签的src属性
    D、不可以引用外部网站的JS文件
3、<script>标签引入外部文件时，()属性必须要设定。
    A、type    B、src    C、charset    D、async
4、编码：
    在页面上输出：我是新开普的学员，正在学习HTML5的课程。
5、编码：
    在信息提示框显示：我是新开普的学员，正在学习HTML5的课程。
```

## part 3

```html
1、以下()是正确的标识符命名。
    A、2a    B、w23%    C、var    D、y45  $    E、y45$
2、JavaScript中的()是严格区分大小写的。
    A、变量    B、类名    C、操作符    D、标签名
3、下面()可以是标识符的命名的字符。
    A、字母    B、下划线    C、美元符    D、#
4、JavaScript中注释有()。
    A、单行注释  B、多行注释  C、文本注释  D、域注释
5、对于变量的说法正确的是()。
    A、变量必须用var声明    B、变量必须先声明后使用
    C、变量的值不可以改变    D、变量的命名区分大小写
6、对于变量的赋值正确的说法是()。
    A、变量可以只声明，不赋值    B、可以把一个字符串赋给一个变量
    C、可以把一个变量的值直接赋给另一个变量    D、变量的数据类型不可以改变
```

## part 4

```html
练习1:求面积公式
页面输出:
    矩形的长为(变量a的值)；
    矩形的宽为(变量b的值)；
    点击按钮弹出框内容:
    计算的矩形面积为：(长*宽)

练习2:鸡兔同笼问题
    《孙子算经》是唐初作为“算学”教科书的著名的《算经十书》之一，共三卷，上卷叙述算筹记数的制度和乘除法则，中卷举例说明筹算分数法和开平方法，都是了解中国古代筹算的重要资料。下卷收集了一些算术难题，“鸡兔同笼”问题是其中之一。原题如下：令有雉（鸡）兔同笼，上有三十五头，下有九十四足。
作业要求，用学过的知识在HTML文档输出下列内容：
(温馨提示：使用JS数据类型计算，用HTML输出)
    头的总数为：35；    脚的总数为：94；
    计算得出鸡的数量为：x 只；    计算得出兔的数量为：y 只；
提示:
解法1：
    （总脚数－鸡的脚数×总只数）÷（兔的脚数－鸡的脚数）=兔的只数
    总只数－兔的只数=鸡的只数
解法2：
    总脚数÷2—总头数=兔的只数
    总只数—兔的只数=鸡的只数

1、JavaScrip中有()数据类型
    A、String  B、Boolean  C、Number  D、Object
2、下面值为()。
    var k=23.45;
    alert(typeof(k));
    A、string  B、boolean  C、number  D、object
3、下面值为()。
    var k=new Object();
    alert(typeof(k));
    A、string  B、boolean  C、number  D、object
4、下面值为()
    alert(typeof('23.45'))
    A、string  B、boolean  C、number  D、object
```

## part 5

```html
1、下面表达式box的值为()。
    var box = 100 +false*2;
    A、100  B、102  C、NaN  D、undefined  E、Infinity
2、下面表达式box的值为()。
    var box = 100 +true*2;
    A、100  B、102  C、NaN  D、undefined  E、Infinity
3、字符’0’对应的ASCII码值：
    A、48  B、49  C、65  D、97
4、字符’A’对应的ASCII码值：
    A、48  B、49  C、65  D、97
5、字符’a’对应的ASCII码值：
    A、48  B、49  C、65  D、97
6、表达式'200'===200的值为()
    A、true  B、false  C、0  D、1
7、表达式'200'==200的值为()
    A、true  B、false  C、0  D、1
8、表达式NaN == NaN 和表达式null == undefined的值分别为();
    A、true  false  B、false true  C、true true   D、false false
9、表达式
    var a1="3";
    alert(a1++ + 7); 
    alert(++a1);
    其值分别为()
    A、10   5  B、11  5  C、10  4  D、11  4
10、对于表达式var box = 3 > 2 ? '对' : '错';box的值为()。
    A、'对'    B、'错'   C、语法错误   D、11  null
```

## part 6

```html
1、使用循环语句输出1-50里所有3的倍数的数字

2、利用循环语句页面上打印出直角三角形。
    *
    **
    ***
    ****
    *****

3、使用语句判断月份是31天还是30天
    两点提示：
        使用switch多条件判断语句 、使用if多分支语句
        合理的省略break优化代码
        弹出 月份为X，该月天数为31（30）

4、本金10000元存入银行，年利率是千分之三，每过1年，将本金和利息相加作为新的本金。计算5年后，获得的本金是多少？ 

5、九九乘法口诀

6、编写程序，求出1-100之间所有除以3余1的数，并求和。

7、判断一个年份是闰年还是平年
	闰年：能被4整除，但不能被100整除的年份 或者 能被400整除的年份

8、计算1-100之间能3整除的数的和

9、计算1-100之间不能被7整除的数的和

10、有个人想知道，一年之内一对兔子能繁殖多少对？于是就筑了一道围墙把一对兔子关在里面。已知一对兔子每个月可以生一对小兔子，而一对兔子从出生后第3个月起每月生一对小兔子。假如一年内没有发生死亡现象，那么，一对兔子一年内（12个月）能繁殖成多少对？（兔子的规律为数列，1，1，2，3，5，8，13，21）

11、求200-300之间所有的奇数的和（用continue）

12、求200-300之间第一个能被7整数的数（break）

13、数组练习
    求一组数中的所有数的和和平均值
    求一组数中的最大值和最小值，以及所在位置
    将字符串数组用|或其他符号分割
    翻转数组
    冒泡排序，从小到大
```


---

<a id="p2"></a>

# 第2篇 · JavaScript函数与对象

---

<a id="p2-1"></a>
# 一、JavaScript函数

**为什么要有函数?**

```js
如果要在多个地方求1-100之间所有数的和，应该怎么做？
```

## 1.1、JavaScript函数的定义

### 1.1.1、函数概念

​	函数是由**事件驱动的或者当它被调用时**执行的**可重复使用的代码块**。通俗来讲：把一段相对独立的具有特定功能的代码块封装起来，形成一个独立实体，就是函数，起个名字（函数名）。

​	函数的作用就是封装一段代码，将来可以重复使用

​	函数就是包裹在花括号中的代码块：

### 1.1.2、函数语法

- 函数声明

```js
function 函数名(参数列表){
    // 函数体
}
```

- 函数表达式

```js
var fn = function () {
  // 函数体
}
```

- 特点：

  函数声明的时候，函数体并不会执行，只要当函数被调用的时候才会执行。

  函数一般都用来干一件事情，函数名称一般使用动词

## 1.2、JavaScript声明式函数的应用

函数的应用分为两步，一是先声明一个函数，再调用该函数。

> **声明函数：**
>
> 1、声明无参函数语法
>
> 2、声明有参函数的语法
>
> 3、声明带有返回值的函数

### 1.2.1、函数的调用

- 调用函数的语法：

```js
函数名();
```

- 特点：

  函数体只有在调用的时候才会执行，调用需要()进行调用。
  可以调用多次(重复使用)

在JavaScript中，调用函数时，如果没有返回值，就直接用函数方法名()调用。如果有参数，则必须给每个参数赋值，函数方法名(参数值)，如果还有返回值，可以用一个变量来存储这个值。

**代码示例：**

```javascript
// 声明无参函数：无参函数就是在函数名的小括号中不定义任何参数。
function sayHello() {
  console.log("吃了没？");
}
// 调用无参函数
sayHello();

// 求1-100之间所有数的和
function getSum() {
  var sum = 0;
  for (var  i = 0; i < 100; i++) {
    sum += i;
  }
  console.log(sum);
}
// 调用
getSum();
```

### 1.2.2、函数的参数

- 为什么要有参数

```javascript
function getSum() {
  var sum = 0;
  for (var i = 1; i <= 100; i++) {
    sum += i;
  }
  console.log();
}

// 虽然上面代码可以重复调用，但是只能计算1-100之间的值
// 如果想要计算n-m之间所有数的和，应该怎么办呢？
```

- 语法：

```javascript
// 函数内部是一个封闭的环境，可以通过参数的方式，把外部的值传递给函数内部
// 带参数的函数声明
function 函数名(var1, var2...) {
  // 函数体
}

上面的var1,var2就是参数，它代表一个不确定的值，这个值要参与函数代码块的运算，在调用函数时，可以给这些参数赋值。也可以在函数中定义多个参数，每个参数之间逗号 (,) 分隔：

当声明函数时，参数相当于作为变量来声明。

变量和参数必须以一致的顺序出现。第一个变量就是第一个被传递的参数的给定的值，以此类推。

// 带参数的函数调用
函数名(实参1, 实参2, 实参3); 
形参1 = 实参1
形参2 = 实参2
```

- 形参和实参

  > 1. 形式参数：在声明一个函数的时候，为了函数的功能更加灵活，有些值是固定不了的，对于这些固定不了的值。我们可以给函数设置参数。这个参数没有具体的值，仅仅起到一个占位置的作用，我们通常称之为形式参数，也叫形参。
  > 2. 实际参数：如果函数在声明时，设置了形参，那么在函数调用的时候就需要传入对应的参数，我们把传入的参数叫做实际参数，也叫实参。

  需要注意的是，同一个函数，形参和实参是一一对应的。

  ​      **思考：如何区分实参和形参？**
  ​            1、出现的地方不一样，一个是在函数的声明中，一个出现在函数的调用中。

  ​            2、代表的意义不一样，一个是声明一个变量，一个是该变量的值。

```javascript
// 定义变量x和y
var x = 5, y = 6;
// 调用fn函数,把x和y传递到函数里面
fn(x,y); 

function fn(a, b) {
  console.log(a + b);
}
// x,y实参，有具体的值。函数执行的时候会把x,y复制一份给函数内部的a和b，函数内部的值是复制的新值，无法修改外部的x,y
```

**代码示例:**

```js
// - 圆的面积 = pi * r * r;
function getArea(r) {
    var pi = 3.1415926;
    console.log(pi * r * r);
}
getArea(7);

// - 求2个数中的最大值
function getMax(a, b) {
    if (a > b) {
        console.log(a);
    } else {
        console.log(b);
    }
}
var x = 100;
var y = 1000;
getMax(x, y);

// - 求3个数中的最大值
function getMax(a, b, c) {
    if (a > b && a > c) {
        console.log(a);
    } else if (b > a && b > c) {
        console.log(b);
    } else if (c > a && c > b) {
        console.log(c);
    }
} 

getMax(11111, 100, 1000);

// 求n个数的最大值？
function getMax(arr) {
    // 参数arr  是数组
    var max = arr[0];
    for (var i = 1; i < arr.length; i++) {
        // 判断max和数组中之后的每一个元素进行比较
        if (max < arr[i]) {
            max = arr[i];
        }
    }
    console.log(max);
}
var array = [12, 2, 45, 1, 10];
getMax(array);

// - 判断一个数是否是素数(又叫质数，只能被1和自身整数的数)
function jdugePrimeNumber(number) {
    // 假设number是质数
    var isPrime = true;
    for (var i = 2; i < number; i++) {
        // 判断是否有能被number整数的数
        if (number % i === 0) {
            // 如果此处执行了。说明不是质数
            isPrime = false;
            break;
        }
    }
    if (isPrime) {
        console.log('质数');
    } else {
        console.log('不是质数');
    }
}
jdugePrimeNumber(13);
```

### 1.2.3、函数的返回值

当函数执行完的时候，并不是所有时候都要把结果打印。我们期望函数给我一些反馈（比如计算的结果返回进行后续的运算），这个时候可以让函数返回一些东西，也就是返回值。函数通过return返回一个返回值。

**语法如下：**

```js
//声明一个带返回值的函数
function 函数名(形参1, 形参2, 形参3...) {
  //函数体
  return 返回值;
}

//可以通过变量来接收这个返回值
var 变量 = 函数名(实参1, 实参2, 实参3...);
```

函数的调用结果就是返回值，因此我们可以直接对函数调用结果进行操作。

示范：利用函数计算两个数相乘后的值，并返回。

```js
//1、声明一个带参数的方法
function myFunction(a,b) {
	return a*b;
}
//2、调用带参的方法
var mul=myFunction(5,6);
```

**代码示例:**

```js
// - 求一组数中的最大值
function getMax(arr) {
    var max = arr[0];
    for (var i = 1; i < arr.length; i++) {
        if (max < arr[i]) {
            max = arr[i];
        }
    }
    // 函数的返回值
    return max;
}

// 可以通过一个变量接受函数的返回值
var array = [12, 1, 99, 10, 20];
var max = getMax(array);
console.log(max);

// 返回值直接参与运算 
var num = 5;
var result = getMax(array) + num;
console.log(result);

// - 求阶乘   5 * 4 * 3 * 2 * 1
function getJieCheng(n) {
    var result = 1;
    for (var i = 1; i <= n; i++) {
        // result *= i;
        result = result * i;
    }
    return result;
}

var num = getJieCheng(5);
console.log(num);


// - 求1!+2!+3!+....+n!    n!
function getJieCheng(n) {
    var result = 1;
    for (var i = 1; i <= n; i++) {
        // result *= i;
        result = result * i;
    }
    return result;
}

function getSum(n) {
    // 求1-n之间每一个数的阶乘的累加
    var sum = 0;
    for (var i = 1; i <= n; i++) {
        // 累加的是每一个数的阶乘
        sum += getJieCheng(i);
    }
    return sum;
}

function getFactorial(num) {  
    var sum = 0; //保存阶乘的值
    for(var i = 1;i <= num;i++){
        var factorial = 1; //千万不要像求和定义为0,否则所有的阶乘结果都是0
        for(var j = 1;j <= i;j++){
            factorial *= j;
        }
        sum += factorial;
    }
    return sum;
}
// // 第一次循环  i = 1    sum = 0 + 1 
// // 第二次循环  i = 2    sum = 1! + 2!

// // 1! + 2! + 3! + 4! + 5!
```

![1572861181047](images02_object/1572861181047.png)

> 需要注意的是，仅仅希望退出函数时 ，也可使用 return 语句。返回值是可选的：
> function myFunction(a,b){
> ​    if (a>b){
> ​        return;
> ​    }
> ​    x=a+b
> }
> 如果 a 大于 b，则上面的代码将退出函数，并不会计算 a 和 b 的总和。

**返回值详解：**

```js
如果函数没有显示的使用 return语句 ，那么函数有默认的返回值：undefined
如果函数使用 return语句，那么跟再return后面的值，就成了函数的返回值
如果函数使用 return语句，但是return后面没有任何值，那么函数的返回值也是：undefined
函数使用return语句后，这个函数会在执行完 return 语句之后停止并立即退出，也就是说return后面的所有其他代码都不会再执行。

推荐的做法是要么让函数始终都返回一个值，要么永远都不要返回值。
```

### 1.2.4、函数是一种数据类型

```javascript
function fn() {}
console.log(typeof fn);
```

- 函数作为参数

因为函数也是一种类型，可以把函数作为另一个函数的参数，在另一个函数中调用

- 函数做为返回值

因为函数是一种类型，所以可以把函数可以作为返回值从函数内部返回。

```javascript
function fn(b) {
  var a = 10;
  return function () {
    alert(a+b);
  }
}
fn(15)();
```

## 1.3、JavaScript arguments对象

​	JavaScript中，arguments对象是比较特别的一个对象，实际上是当前函数的一个内置属性。也就是说所有函数都内置了一个arguments对象，arguments对象中存储了传递的所有的实参。arguments是一个伪数组，因此就可以进行遍历。

**示例代码:**

```js
// 求任意个数的最大值
function getMax() {
    var max = arguments[0];
    for (var i = 1; i < arguments.length; i++) {
        if (max < arguments[i]) {
            max = arguments[i];
        }
    }
    return max;
}

var max = getMax(5, 10, 1, 5, 100);
console.log(max);


// 求任意个数的和
function getSum() {
    var sum = 0;
    for (var i = 0; i < arguments.length; i++) {
        sum += arguments[i];
    }
    return sum;
}

var sum = getSum(5, 1, 3, 4);
console.log(sum);

// 求斐波那契数列Fibonacci中的第n个数是多少？      1 1 2 3 5 8 13 21...
function getFib(n) {
    // 函数体
    var n1 = 1;
    var n2 = 1;
    var n3;
    for (var i = 3; i <= n; i++) {
        n3 = n1 + n2;
        n1 = n2;
        n2 = n3;
    }
    return n3;
}

var r = getFib(6);
console.log(r);
```

## 1.4、JavaScript函数作用域

**变量从作用域的角度划分，分为两种：局部变量和全局变量。**

**什么是作用域?**

​	变量可以起作用的范围

### 1.4.1、局部变量

​	在JavaScript函数内部声明的变量是局部变量，所以只能在函数内部访问它，该变量的作用域是局部的。

​	可以在不同的函数中使用名称相同的局部变量，因为只有声明过该变量的函数才能识别出该变量。只要函数运行完毕，局部变量就会被删除。

```js
function sayHello(){
	//该变量声明在一个函数内部，name就是一个局部变量，
	//局部变量只可以在本函数内调用
	var  name="H5";
	alert("Hello "+name);
}
```

### 1.4.2、全局变量

​	在函数外声明的变量是*全局*变量，网页上的所有脚本和函数都能访问它。

```js
//声明一个全局变量，任何函数都可以使用它
var  name="H5";
function sayHello(){
    alert("Hello "+name);
}
//调用函数
sayHello();
```

​	需要注意的是，如果没有使用var声明变量，该变量将被自动作为全局变量声明，不推荐使用。

​	比如这条语句：carname="Volvo";将声明一个全局变量 carname，即使它在函数内部声明。

### 1.4.3、变量的生命周期

​	JavaScript 变量的生命期从它们被声明的时间开始。

​	局部变量会在退出作用域之后会销毁。

​	全局变量会在关闭网页或浏览器才会销毁。

### 1.4.4、局部变量和全局变量的区别

1、声明位置不同

​      局部变量声明在函数内部。全局变量声明在函数外部

2、作用域不一样

​      局部变量只在某一个局部范围有效，比如函数内部。全局变量在整个页面有效，网页上的所有脚本和函数都能访问它。

3、生命周期不一样

​      局部变量会在函数运行以后被删除，全局变量会在页面关闭后被删除

### 1.4.5、块级作用域

任何一对花括号（｛和｝）中的语句集都属于一个块，在这之中定义的所有变量在代码块外都是不可见的，我们称之为块级作用域。

**在es5之前没有块级作用域的的概念,只有函数作用域**，现阶段可以认为JavaScript没有块级作用域

### 1.4.6、作用域链

只有函数可以制造作用域结构， 那么只要是代码，就至少有一个作用域, 即全局作用域。凡是代码中有函数，那么这个函数就构成另一个作用域。如果函数中还有函数，那么在这个作用域中就又可以诞生一个作用域。

将这样的所有的作用域列出来，可以有一个结构: 函数内指向函数外的链式结构。就称作作用域链。

```js
// 案例1：
function f1() {
    function f2() {
    }
}

var num = 456;
function f3() {
    function f4() {    
    }
}
```

![](images02_object/微信截图_20200706143354.png)

```js
// 案例2
function f1() {
    var num = 123;
    function f2() {
        console.log(num); 
    }
    f2();
}
var num = 456;
f1();
```

![](images02_object/微信截图_20200706143537.png)

## 1.5、匿名函数

匿名函数，就是没有名字的函数。

一般的**有名函数:**

```js
function  myFun( a,b ){
    console.info( a+b );
}
myFun( 10 , 30 );  // 输出40
```

**匿名函数:** 有关键词 function， 有小括号，有大括号，就是没有函数名。

```js
function(a,b){
    console.info( a+b );
}
```

想要执行它，怎么执行？没有名字，怎么调用？

**方式一：**把它放进一个变量里，这个变量就相当于一个函数名了。没有名字的匿名函数，变成有“名”函数了，我们把这种方式称之为**函数字面量**。

```js
var  myFun = function( a,b ){
    console.info( a+b);
};

myFun( 10,30 );
```

**方式二：**干脆不要名字，直接执行~！-- 这么做可以在内部形成局部变量和局部函数，防止全局污染。

个人常用的直接执行匿名函数的方式！

**(**匿名函数**)();**

**(**匿名函数**() );**

```js
//注意: 使用改写法一定要注意添加分号
(function(a,b){
	console.info( a+b );
})(10,30);

(function(a,b){
	console.info( a+b );
}(10,30));
```

其他直接调用的方式显得比较怪异了。

```js
// 在function前面加一元操作符号  
!function () { /* code */ } ();  
~function () { /* code */ } ();  
-function () { /* code */ } ();  
+function () { /* code */ } ();

// 在function前面添加 new 关键词
new function () { /* code */ }  
new function () { /* code */ } () // 如果需要传递参数，只需要加上括弧()
```

**方式三：**利用事件去调用。

```js
var  btn = document.getElementById("btn");  // 找到页面某个标签

// 添加事件
btn.onclick = function(){
	console.info("你点了我！");
}
```

**方法四：**作为对象的方法调用

```js
var  myObj = {
	name : "John",
	sayHello:function(){
		console.info("Hello,"+ this.name );
	}
};

myObj.sayHello();
```

**方法五：**作为另一个函数的参数。

**函数也可以作为另一个函数的参数的。**当然有名函数也可以做参数。

```js
function myFun(fn){
    fn();
}

myFun(function(){
    console.info("这个匿名函数是个参数");
});
```

## 1.6、构造函数

​	通过  new 函数名    来实例化对象的函数叫构造函数。任何的函数都可以作为构造函数存在。之所以有构造函数与普通函数之分，**主要从功能上进行区别的，构造函数的主要 功能为 初始化对象，特点是和new 一起使用。new就是在创建对象，从无到有，构造函数就是在为初始化的对象添加属性和方法**。**构造函数定义时首字母大写**（规范）。

​	对new理解：new 申请内存, 创建对象,当调用new时，后台会隐式执行new Object()创建对象。所以，通过new创建的字符串、数字是引用类型，而是非值类型。

**1、常用的构造函数：**

```js
1. var arr = [];     为      var arr = new Array();       的语法糖。
2. var obj = {}     为      var obj = new Object();     的语法糖
3. var date = new Date();
4. ...
```

**2、自定义构造函数:**

```js
// 1. 构造函数名首字母要大写
// 2. 构造函数的作用就是用来创建对象的,
// 3. 功能上: 普通函数是用来执行某个行为;构造函数是用来创建对象的
// 4. 语法上: 基本没有差别
// 5. 从函数体: 普通函数的函数体里面就是要执行的逻辑代码; 构造函数的函数体里面是用来初始化对象成员以及对象方法的;
function Person(id,name,age) {
    //this关键字: 表示的当前对象
    this.id = id;   //对象的属性
    this.name = name;
    this.age = age;
    this.eat = function () {  //对象方法
        alert(this.name+"的吃饭行为");
    }
}

//直接通过函数名() 调用的是普通函数

//使用构造函数,必须结合new来使用
//Person()就算是构造函数,它也属于函数的一种
var p1 = new Person(1001,"张三",12); //创建一个Person对象

var p2 = new Person(1002,"李四",12);

document.write("p1的name是:"+p1.name+"<br>");

p1.eat();
```

## 1.7、回调函数

​      我们先来看看回调的英文定义：A callback is a function that is passed as an argument to another function and is executed after its parent function has completed。

​      **字面上的理解，回调函数就是一个参数，将这个函数作为参数传到另一个函数里面，当那个函数执行完之后，再执行传进去的这个函数。这个过程就叫做回调**。

​      其实也很好理解对吧，回调，回调，就是回头调用的意思。主函数的事先干完，回头再调用传进来的那个函数。

​      举一个别人举过的例子：约会结束后你送你女朋友回家，离别时，你肯定会说：“到家了给我发条信息，我很担心你。” 对不，然后你女朋友回家以后还真给你发了条信息。小伙子，你有戏了。其实这就是一个回调的过程。你留了个参数函数（要求女朋友给你发条信息）给你女朋友，然后你女朋友回家，回家的动作是主函数。她必须先回到家以后，主函数执行完了，再执行传进去的函数，然后你就收到一条信息了。

```js
function modifyArray(arr, callback) {
 // 对 arr 做一些操作
 arr.push(100);
 // 执行传进来的 callback 函数
 callback();
}
var arr = [1, 2, 3, 4, 5];
modifyArray(arr, function() {
 console.log("array has been modified", arr);
});
```

​	上面的代码中，我们先定义了主函数和回调函数，然后再去调用主函数，将回调函数传进去。

​	定义主函数的时候，我们让代码先去执行callback()回调函数，但输出结果却是后输出回调函数的内容。这就说明了主函数不用等待回调函数执行完，可以接着执行自己的代码。所以一般回调函数都用在耗时操作上面。比如ajax请求，比如处理文件等。

## 1.8、预解析

JavaScript代码的执行是由浏览器中的JavaScript解析器来执行的。JavaScript解析器执行JavaScript代码的时候，分为两个过程：预解析过程和代码执行过程

### 1.8.1、执行环境

​	执行环境定义了变量和函数有权访问的其他数据，决定了他们各自的行为。每个执行环境都有与之对应的变量对象（variable object），此对象保存着环境中定义的所有变量和函数。我们无法通过代码来访问变量对象，但是解析器在处理数据时会在后台使用到它。

**全局执行环境:**

​	全局执行环境是最外围的一个执行环境，根据ECMAScript实现所在的宿主环境不同，表示执行环境的对象也不同。**在web浏览器中，我们可以认为它是window对象，因此所有的全局变量和函数都是作为window对象的属性和方法创建的**。代码载入浏览器时，全局环境被创建，应用程序退出，如关闭网页或者浏览器时，全局执行环境被销毁。

**函数执行环境:**

​	每个函数都有自己的执行环境，当执行流进入一个函数时，函数的环境就被推入一个环境栈中，当函数执行完毕后，栈将其环境弹出，把控制权返回给之前的执行环境。

### 1.8.2、预解析过程

1. 把变量的声明提升到当前作用域的最前面，只会提升声明，不会提升赋值。
2. 把函数的声明提升到当前作用域的最前面，只会提升声明，不会提升调用。
3. 先提升var，再提升function。

### 1.8.3、变量提升（hoisting）

ES5 提升有变量提升和函数提升。

**原则：**

​	1、所有声明都会被提升到作用域的最顶上；

​	2、同一个变量声明只进行一次，并且因此其他声明都会被忽略；

​	3、函数声明的优先级优于变量申明，且函数声明会连带定义一起被提升。

**变量提升：**

​	把变量声明提升到函数的顶部，但是变量赋值不会提升。

```js
console.log(a);
var a = 10;
//输出为undefined

//与上例等价
var a;
console.log(a);
a = 10;
```

​	注意：变量未声明，直接使用，输出‘变量 is not defined。

**函数提升:**

​	函数提升会将函数声明连带定义一起提升。

​	在JavaScript中函数的创建方式有三种：函数声明、函数表达式（函数字面量）、函数构造法（动态的，匿名的）。

​	只有函数声明创建的函数会执行函数提升，字面量定义的函数（实质为变量+匿名函数）会执行变量提升。

```js
test1();
function test1(){
    console.log("可以被提升");
}
```

```js
test2();
var test2 = function(){
    console.log("不可以被提升");
}
```

```js
console.log(test2);
var test2 = function(){
   console.log("不可以被提升");
}
```

函数和变量同时提升:

```js
console.log(test3);
function test3(){console.log('func');}
var test3 = 'Mary';
```

## 1.9、防止全局污染

### 1.9.1、全局污染问题:

​	JavaScript 可以随意定义保存所有应用资源的全局变量。

​	但全局变量可以削弱程序灵活性，增大了模块之间的耦合性。在多人协作时，如果定义过多的全局变量 有可能造成全局变量冲突，也就是全局变量污染问题。

### 1.9.2、解决全局污染

```js
// 方式1: 定义全局变量命名空间,只创建一个全局变量，并定义该变量为当前应用容器，把其他全局变量追加在该命名空间下。

//my就是一个全局变量,我们可以把my这个全局变量当成一个命名空间,然后把其他的所有全局变量都放在它下面;
var my={};  //唯一的全局变量
my.name={
    big_name:"zhangsan",
    small_name:"lisi"
};
my.work={
    school_work:"study",
    family_work:"we are"
};

// alert(my.name.small_name);

// 方式2: 利用匿名函数将脚本包裹起来
(function(){
    var temp = {};
    //把两个变量赋值给temp
    //temp.school_work = "study";
    //temp.small_name = "李四";
    small_name = "李四";
    temp.getName = function(){
        return small_name;
    }

    //把tmep赋值给全局变量test
    window.test = temp;
}())
// alert(test.getName());
```

<a id="p2-2"></a>
# 二、JavaScript对象

## 2.1、类和对象的概念

### 2.1.1、为什么要有对象

```js
function printPerson(name, age, sex....) {
}
// 函数的参数如果特别多的话，可以使用对象简化
function printPerson(person) {
  console.log(person.name);
  ……
}
```

###  2.1.2、什么是对象

​	所谓**对象就是真实世界中的实体，对象与实体是一一对应的，也就是说现实世界中每一个实体都是一个对象，它是一种具体的存在**，可以发现身边很多对象，汽车，狗，人等，这些对象都有一个属性和行为。

​	比如一只狗，那么它的属性有名称、品种、颜色、体重；行为有吠叫、摇摆、跑等。

### 2.1.3、JavaScript中的对象

​	**JavaScript语言没有“类”，而改用构造函数（constructor）作为对象的模板**。前面说过，“对象”是单个实物的抽象。所以，通常需要一个模板，表示某一类实物的共同特征，然后“对象”根据这个模板生成。**所谓“构造函数”，就是专门用来生成“对象”的函数。它提供模板，作为对象的基本结构**。比如var date1=new Date()是通过调用Date的构造函数Date()(这里可以理解为一个类)来创建一个日期对象。一个构造函数，可以生成多个对象，这些对象都有相同的属性和行为，但是属性值可以不同。

​	在 JavaScript 中，不会创建类，也不会通过类来创建对象（就像在其他面向对象的语言中那样），JavaScript 基于 prototype(原型)，而不是基于类的。

​	在Javascript没有类和接口，只有对象，而根据ECMAscript的定义，对象是“无序属性的集合，其属性包含基本值，对象或者函数”。

​	需要注意的是，在ECMAscrip6.0中，已经使用class来定义类了。	

​	对象object是JavaScript的核心概念，也是最重要的数据类型。**JavaScript的所有数据都可以被视为对象。对象是一个容器，封装了属性(propert)和方法(method)。所谓属性，就是对象的静态状态；所谓方法，就是对象的动态行为**。

​	JavaScript的对象是无序属性的集合。

​	其属性可以包含基本值、对象或函数。对象就是一组没有顺序的值。我们可以把JavaScript中的对象想象成键值对，其中值可以是数据和函数。

​	对象的行为和特征

​		特征---属性：事物的特征在对象中用属性来表示。

​		行为---方法：事物的行为在对象中用方法来表示。

在JavaScript中，其中一种定义对象的方法如下：

```js
var o = {
    p: "Hello World",
    sayHello:function(){
        return p;
    }
};
```

​      上面代码中，定义了一个对象o,这个对象内部包含**2个键值对:p和sayHello**，其中**p键值对是描述静态属性的;sayHello键值对是描述对象的动态行为的**。属性名与属性值之间用冒号分隔。

​      p是对象的属性名，字符串“Hello World”是对象的属性值。sayHello是对象的另一个属性名，属性值是function(){return p; }。

​      如果对象内部包含多个属性对，每个属性对之间用逗号分隔。 需要注意的是，**上面的代码后台隐式调用了new Object()这个构造函数创建了一个对象o,再通过键值对定义静态属性动态行为**。

​      对象又分内置对象和自定义对象，其中内置对象是指JavaScript中已经定义好的，比如我们之后学的Date、Array、Math、String等，这些内置对象提供了许多方法和属性,只管调用和使用即可,比如Math对象中的PI和E是属性，pow(x,y)、sin(x)、sqrt(x)等方法。

​      而在这一小节里，主要介绍自定义对象的使用。

## 2.2、对象的使用

### 2.2.1、对象的创建方式

- 对象字面量

```javascript
var hero = {
    name: '黄忠',
    weapon: '弓箭',
    equipment: ['头盔', '靴子', '盔甲'],
    blood: 100,
    attack: function () {
        console.log(this.name + '：射箭');
    },
    run: function () {
        console.log(this.name + ': 加速跑');
    }
}
console.log(hero.name);
console.log(hero.equipment);

hero.attack();
hero.run(); 
```

- new Object()创建对象

```javascript
// Object 是一个构造函数
// new 的方式来调用构造函数
// new Object() 调用构造函数   会在内存中创建一个对象
var hero = new Object(); // 创建了一个空的对象
// 打印一个不存在的属性 输出 undefined
// console.log(hero.name);
// 属性
// JavaScript的动态特性
hero.name = '关羽';
hero.weapon = '青龙偃月刀';
hero.equipment = ['头盔', '靴子', '赤兔马'];
hero.blood = 100;
// 方法
hero.attack = function () {
    console.log(this.name + ': 射箭');
}
hero.run = function () {
    console.log(this.name + ': 加速跑')
}
```

- 工厂函数创建对象

```javascript
function createHero(name, weapon, equipment, blood) {
    var hero = new Object(); //返回一个空的对象
    // 属性
    hero.name = name;
    hero.weapon = weapon;
    hero.equipment = equipment;
    hero.blood = blood;
    // 方法
    hero.attack = function () {
        console.log(this.name + '：攻击');
    }
    hero.run = function () {
        console.log(this.name + '：加速跑');
    }
    return hero;
}

var hero1 = createHero('黄忠', '弓箭', ['头盔', '靴子'], 100);
var hero2 = createHero('刘备', '剑', ['头盔', '盔甲'], 100);
```

- 自定义构造函数

```javascript
function Hero(name, weapon, equipment, blood) {
    // this 动态的给对象增加成员
    // this 指向了当前对象
    this.name = name;
    this.weapon = weapon;
    this.equipment = equipment;
    this.blood = blood;

    this.attack = function () {
        console.log(this.name + '：攻击');
    }
    this.run = function () {
        console.log(this.name + ': 加速跑');
    }
}

var hero1 = new Hero('黄忠', '弓箭', ['头盔', '靴子'], 100);
var hero2 = new Hero('刘备', '剑', ['头盔', '盔甲'], 100);
```

​     **this代表的是当前对象**。

但是构造函数方有个缺点，就是对象的方法放在了构造函数内部，这样每创建一个方法就会需要多占用一些内存，所以js给构造函数设计了一个**prototype**属性，用来存放对象的方法：

```js
function Student(name,age,id){
    this.name=name;
    this.age=age;
    this.id=id;
}
Student.prototype={
    work:function(skill){
        alert(this.name+"做"+skill+"开发相关的工作");
    },
    classId:"Java1班"
}
var stu1=new Student("李明",18,20151515);//得到的就是字面量对象
var stu2=new Student("王磊",18,20141000);//得到的就是字面量对象	

console.log(stu2.work==stu1.work);//ture，节省了内存空间
stu1.work("Java");
stu2.work("PHP");
console.log(stu1.classId);//20151515
console.log(stu2.classId);//20141000
```

### 2.2.2、属性和方法

​	如果一个变量属于一个对象所有，那么该变量就可以称之为该对象的一个属性，属性一般是名词，用来描述事物的特征。
​	如果一个函数属于一个对象所有，那么该函数就可以称之为该对象的一个方法，方法是动词，描述事物的行为和功能。

### 2.2.3、关键字详解

#### new关键字

> 构造函数 ，是一种特殊的函数。主要用来在创建对象时初始化对象， 即为对象成员变量赋初始值，总与new运算符一起使用在创建对象的语句中。

1. 构造函数用于创建一类对象，首字母要大写。
2. 构造函数要和new一起使用才有意义。

```js
// Student 自定义构造函数
// 属性：name age sex score
// 方法：sayHi
function Student(name, age, sex, score) {
    // 属性
    this.name = name;
    this.age = age;
    this.sex = sex;
    this.score = score;
    // 方法
    this.sayHi = function () {
        console.log(this.name + ': hello');
    }
}

var stu1 = new Student('lilei', 18, '男', 100);
var stu2 = new Student('hanmeimei', 17, '女', 100);
```

new在执行时会做四件事情

```html
new会在内存中创建一个新的空对象
new 会让this指向这个新的对象
执行构造函数  目的：给这个新对象加属性和方法
new会返回这个新对象
```

#### this详解

```html
JavaScript中的this指向问题，有时候会让人难以捉摸，随着学习的深入，我们可以逐渐了解
现在我们需要掌握函数内部的this几个特点
	1. 函数在定义的时候this是不确定的，只有在调用的时候才可以确定
	2. 一般函数直接执行，内部this指向全局window
	3. 函数作为一个对象的方法，被该对象所调用，那么this指向的是该对象
	4. 构造函数中的this其实是一个隐式对象，类似一个初始化的模型，所有方法和属性都挂载到了这个隐式对象身上，后续通过new关键字来调用，从而实现实例化
```

### 2.2.4、对象的使用方法

**对象属性的使用：**

​	1、可以用点符号访问对象属性值

​	2、也可以通过数组的方式，即用["属性名称"]

**对象方法的使用：**

​	可以使用对象名.方法名()来调用

#### 遍历对象的属性

> 通过for..in语法可以遍历一个对象

```javascript
var obj = {
    name: '张三',
    age: 18,
    sex: true,
    sayHi: function () {
        console.log(this.name);
    }
};
for(var key in obj) {
  console.log(key + "==" + obj[key]);
}
```

#### 删除对象的属性

```javascript
function fun() { 
  this.name = 'mm';
}
var obj = new fun(); 
console.log(obj.name); // mm 
delete obj.name;
console.log(obj.name); // undefined
```

### 简单类型和复杂类型的区别

> 基本类型又叫做值类型，复杂类型又叫做引用类型
>
> 值类型：简单数据类型，基本数据类型，在存储时，变量中存储的是值本身，因此叫做值类型。
>
> ​	Number  String  Boolean  Null  Undefined
>
> 引用类型：复杂数据类型，在存储是，变量中存储的仅仅是地址（引用），因此叫做引用数据类型。
>
> ​	Object	Array	

- 堆和栈	

  ```html
  堆栈空间分配区别：
  　　1、栈（操作系统）：由操作系统自动分配释放 ，存放函数的参数值，局部变量的值等。 
  　　2、堆（操作系统）： 存储复杂类型(对象)，一般由程序员分配释放， 若程序员不释放，由垃圾回收机制回收。
  ```

- **注意：JavaScript中没有堆和栈的概念，此处我们用堆和栈来讲解，目的方便理解和方便以后的学习。**

**基本类型在内存中的存储**

![1498288494687](images02_object/1498288494687.png)

**复杂类型在内存中的存储**

![1498700592589](images02_object/1498700592589.png)

**基本类型作为函数的参数**

![1497497605587](images02_object/1497497605587.png)

**复杂类型作为函数的参数**

![1497497865969](images02_object/1497497865969.png)

```js
// 下面代码输出的结果?
// 构造函数
function Person(name,age,salary) {
  this.name = name;
  this.age = age;
  this.salary = salary;
}

// 普通函数
function f1(person) { // person为形参
  person.name = "lisi"; 
  person = new Person("aa",18,10); 
}

var p = new Person("zhangsan",18,1000);
console.log(p.name); // zhangsan
f1(p); // 把p对应的地址复制一份给person,person和p对应一个地址,那么修改地址对应的内容,会影响p
console.log(p.name); // lisi
```

```js
//1. 
var num1 = 10;
var num2 = num1; // num2 = 10;
num1 = 20;
console.log(num1); // 20
console.log(num2); // 10

//2. 
var num = 50;
function f1(num) {
    num = 60;
    console.log(num);
}
f1(num); // 60
console.log(num); // 50
```

<a id="p2-3"></a>
# 三、JavaScript内置对象

JavaScript中的对象分为3种：内置对象、自定义对象、浏览器对象

JavaScript 提供多个内置对象：Math/Array/Date....

对象只是带有**属性**和**方法**的特殊数据类型。

学习一个内置对象的使用，只要学会其常用的成员的使用（通过查文档学习）

可以通过MDN/W3C来查询

内置对象的方法很多，我们只需要知道内置对象提供的常用方法，使用的时候查询文档。

Mozilla 开发者网络（MDN）提供有关开放网络技术（Open Web）的信息，包括 HTML、CSS 和万维网及 HTML5 应用的 API。

```html
MDN:https://developer.mozilla.org/zh-CN/
```

**如何学习一个方法？**

1. 方法的功能
2. 参数的意义和**类型**
3. 返回值意义和**类型**
4. demo进行测试

## 3.1、Array对象

### 3.1.1、Array构造函数

```js
// new关键字创建空数组
    var arr = new  Array();
// new关键字创建包含元素的数组
    var arr = new  Array(值1,值2.....值N);
// new关键字创建指定元素个数的数组
    var arr = new  Array(数值);
// 也可以使用[]直接创建数组
    var arr = [];
    var arr = [值1,值2.....值N];
// 可以使用length属性获取数组的长度;并且可以给一个数组长度赋值。
```

检测一个对象是否是数组

- instanceof
- Array.isArray()     HTML5中提供的方法，有兼容性问题

函数的参数，如果要求是一个数组的话，可以用这种方式来进行判断；

**sort排序底层源码(了解)：**

```js
function sort(array, fnCompare) {
    // 外层循环 控制趟数
    for (var i = 0; i < array.length - 1; i++) {
        // 假设排好序了
        var isSort = true;
        // 内层循环 控制比较的次数
        for (var j = 0; j < array.length - 1 - i; j++) {

            if (fnCompare(array[j], array[j + 1]) > 0) {
                isSort = false;
                // 交换位置
                var tmp = array[j];
                array[j] = array[j + 1];
                array[j + 1] = tmp;
            }
        }
        // 判断是否排好了
        if (isSort) {
            break;
        }
    }
} 

var arr = [56, 10, 1, 17];


sort(arr, function (a, b) {
    return b - a;
})

console.log(arr);
```

### 3.1.2、Array对象方法

程序运行时通常需要读取数组中的数据，有时候需要对数据进行修改。

（一）读取数据：可以使用索引查询获取数组元素和添加数组元素

（二）添加数据：使用push()方法将新元素添加到数组尾部.

（三）删除数据：可以使用delete()运算符删除指定的元素。

（四）删除末尾元素(更新数据) : pop()方法,该方法会返回删除的元素。

（五）删除顶端的元素 : shift()方法

（六）在数组顶端添加元素 :  unshift()方法,返回值为新数组的长度。

（七）字符转换：toString()方法将数组表示为字符串。

（八）join方法输出数组元素。(输出结果会转换成字符串)

（九）数组逆序reverse()：颠倒数组元素的顺序;返回值为逆序后的新数组。

（十）数组排序 sort：

```js
语法 数组名.sort(sortfunction)
sortfunction若省略，默认为从按照ASII字符顺序进行升序排列
sortfunction必须返回：正值、零、负值三者之一。正直表示第一个值大于第二个值，负值反之，零则相等。
var arr1 = [72,33,12,44,24];
arr1.sort(function(a,b){return a-b;});
alert(arr1);

var arr1 = [72,33,12,44,24];
arr1.sort(function(a,b){return b-a;});
alert(arr1);
```

（十一）扩充数组 concat:将多个数组的元素合并为一个新的数组。

（十二）splice方法：删除、替换、插入元素,会更改原数组
​      第一参数为起始位置索引
​      第二参数为切取元素个数
​      第三个参数为插入元素，可选项

（十三）切取数组的一段元素 slice：
​      切取部分作为新数组返回，不会对原数组改变。
​      第一参数为起始位置索引(包含)
​      第二参数为结束位置索引，注意区分splice(不包含)
​      若省略第二个参数则直接切取到结尾

（十四）toString()/valueOf()

​	toString()		把数组转换成字符串，逗号分隔每一项

​	valueOf()         返回数组对象本身	

**将一个字符串数组输出为|分割的形式，比如“刘备|张飞|关羽”。使用两种方式实现**

```js
function myJoin(array, seperator) {
  if (array.length == 0){
    return '';
  }
  var str = array[0];
  for (var i = 1; i < array.length; i++) {
    str += seperator + array[i];
  }
  return str;
}
var array = [6, 3, 5, 6, 7, 8, 0];
console.log(myJoin(array, '-'));

console.log(array.join('-'))
```

**将一个字符串数组的元素的顺序进行反转。使用两种种方式实现。**

```js
function myReverse(arr) {
  if (!arr || arr.length == 0) {
    return [];
  }
  for (var i = 0; i < arr.length / 2; i++) {
    var tmp = arr[i];
    arr[i] = arr[this.length - i - 1];
    arr[arr.length - i - 1] = tmp;
  }
  return arr;
}

var array = ['a', 'b', 'c'];
console.log(myReverse(array));

console.log(array.reverse());
```

## 3.2、Date对象

Date是JavaScript的内置对象，系统在Date对象中封装了与日期和时间相关的属性和方法。

Date使用UTC1970年1月1日0时开始经过的毫秒数来存储时间。

​	GMT 格林尼治时间

​	UTC 国际协调时间

```html
注:January(Jan.)一月； February(Feb.)二月； March(Mar.)三月； April(Apr.)四月； May五月 June(六月； July（jul）七月； August(Aug.)八月； September(Sep.)九月； October(Oct.)十月； November(Nov.)十一月； December(Dec.)十二月

Monday 星期一 Tuesday 星期二 Wednesday 星期三 Thursday 星期四 Friday 星期五 Saturday 星期六 Sunday 星期日
```

### 3.2.1、Date构造函数

```js
// 无参数的情况下返回值为当前时间。不同浏览器显示的时间格式会有细微差异
var date= new Date();

// 参数为毫秒值,距1970年1月1日（世界标准时间）起的毫秒数
var date = new Date(milliseconds);

// 参数为日期字符串
var date = new Date(dateString);

// 必选值:year, month, day；
var date = new Date(year, month, day, hours, minutes, seconds, milliseconds);
```

### 3.2.2、Date对象方法

**通过使用针对日期对象的方法，我们可以很容易地对日期进行操作**。

```html
getDate()			从 Date 对象返回一个月中的某一天 (1 ~ 31)。

getDay()			从 Date 对象返回一周中的某一天 (0 ~ 6)。

getFullYear()		从 Date 对象以四位数字返回年份。

getHours()			返回 Date 对象的小时 (0 ~ 23)。

getMilliseconds()   返回 Date 对象的毫秒(0 ~ 999)。

getMinutes()        返回 Date 对象的分钟 (0 ~ 59)。

getMonth()			从 Date 对象返回月份 (0 ~ 11)。

getSeconds()		返回 Date 对象的秒数 (0 ~ 59)。

getTime()			返回 1970 年 1 月 1 日至今的毫秒数。

setDate()			设置 Date 对象中月的某一天 (1 ~ 31)。

setFullYear()		设置 Date 对象中的年份（四位数字）。

setHours()			设置 Date 对象中的小时 (0 ~ 23)。

setMilliseconds()   设置 Date 对象中的毫秒 (0 ~ 999)。

setMinutes()		设置 Date 对象中的分钟 (0 ~ 59)。

setMonth()			设置 Date 对象中月份 (0 ~ 11)。

setSeconds()		设置 Date 对象中的秒钟 (0 ~ 59)。

setTime()			以毫秒设置 Date 对象。
```

**Date对象相关的字符串表示方法：**

```html
toSting()			获取Date实例的字符串表示

toDateSting()		获取Date的日期部分字符串表示

toTimeSting()		获取Date的时间部分字符串表示

toLocaleString()    据本地时间格式，把 Date 对象转换为字符串。

toLocaleDateString()    根据本地时间格式，把 Date 对象的日期部分转换为字符串。

toLocaleTimeString()    根据本地时间格式，把 Date 对象的时间部分转换为字符串。

valueOf():			返回1970年1月1日午夜到指定日期的毫秒数

Date.now():			返回1970年1月1日午夜到指定日期的毫秒数(HTML5中提供的方法，有兼容性问题)
```

**Date对象解析相关方法:**

​      Date.parse()返回1970年1月1日午夜到指定日期（字符串）的毫秒数。

​      Date.parse()参数支持的时间格式如下：

​      ​      1/24/2016;得到   Sun Jan 24 2016 10:10:10 GMT+0800

​      ​      格式不正确会返回 无效的时间

**写一个函数，格式化日期对象，返回yyyy-MM-dd HH:mm:ss的形式**

```js
function formatDate(d) {
  //如果date不是日期对象，返回
  if (!d instanceof Date) {
    return;
  }
  var year = d.getFullYear(),
      month = d.getMonth() + 1, 
      date = d.getDate(), 
      hour = d.getHours(), 
      minute = d.getMinutes(), 
      second = d.getSeconds();
  month = month < 10 ? '0' + month : month;
  date = date < 10 ? '0' + date : date;
  hour = hour < 10 ? '0' + hour : hour;
  minute = minute < 10 ? '0' + minute:minute;
  second = second < 10 ? '0' + second:second;
  return year + '-' + month + '-' + date + ' ' + hour + ':' + minute + ':' + second;
}
```

**计算时间差，返回相差的天/时/分/秒**

```js
function getInterval(start, end) {
    var day, hour, minute, second, interval;
    interval = end - start;
    interval /= 1000;
    day = Math.round(interval / 60 / 60 / 24);
    hour = Math.round(interval / 60 / 60 % 24);
    minute = Math.round(interval / 60 % 60);
    second = Math.round(interval % 60);
    return {
        day: day,
        hour: hour,
        minute: minute,
        second: second
    }
}

console.log(getInterval(new Date("2019-12-31"),new Date("2020-5-2")))
```

## 3.3、String对象

​	字符串是非常重要的数据类型，除了基本字符串外，JavaScript还提供了字符串的引用类型--字符串对象。

​	字符串对象提供了字符串检索、替换、连接等方法...

**字符串的不可变**

```js
var str = 'abc';
str = 'hello';
// 当重新给str赋值的时候，常量'abc'不会被修改，依然在内存中
// 重新给字符串赋值，会重新在内存中开辟空间，这个特点就是字符串的不可变
// 由于字符串的不可变，在大量拼接字符串的时候会有效率问题
```

### 3.3.1、String构造函数

​	可以通过new 关键字创建字符串对象

```js
var str=”hello”; // 字符串字面量

var str=new String(); // 字符串对象
```

​	注:创建出来的类型虽说不同,但是对于内置的方法和属性都是可以使用的

​	length 属性返回字符串的长度(字符数)。

### 3.3.2、String对象方法

```js
charAt(index)			返回在指定位置的字符。

charCodeAt()			返回在指定的位置的字符的 Unicode 编码。

concat([string1,string2...)  连接字符串。

slice(start,end)		提取字符串n到m之间的片断(不包括m位置的字符串)，并在新的字符串中返回被提取的部分。

substring(star,end)		提取字符串中两个指定的索引号之间的字符。大多数情况和上一个作用相同，当参数为负值时会有不同，但这种情况较少用，不做讨论，有兴趣的话自己测试或查下资料

substr(start,length)     从起始索引号提取字符串中指定数目的字符。

split(separator,limit)   把字符串分割为字符串数组。

indexOf(subString[, startIndex]) 	检索字符串,返回某个指定的字符串值在字符串中首次出现的位置。注意，如果查找不到会返回 -1

lastIndexOf(subString[, startIndex]) 	返回指定字符串在字符串最后出现的位置。

toLowerCase()    	把字符串转换为小写。

toUpperCase()    	把字符串转换为大写。

match()  	找到一个或多个正则表达式的匹配。(正则表达式后续课程会讲),该方法会返回一个数组，数组中包含了所符合条件的文本。

replace(rgExp, replaceText)  	替换与正则表达式匹配的子串，并返回替换后的字符串，注意原字符串不会改变.

search(rgExp)		回与正则表达式查找内容匹配的第一个子字符串的位置。(与indexOf相似)

需要注意的是，JavaScript 的字符串是不可变的（immutable），String 类定义的方法都不能改变字符串的内容。像 String.toUpperCase() 这样的方法，返回的是全新的字符串，而不是修改原始字符串。
```

**把字符串中所有的o替换成!**

```js
var s = 'abcoefoxyozzopp';
var index = -1;
do {
  index = s.indexOf('o', index + 1);
  if (index !== -1) {
    // 替换
    s = s.replace('o', '!');
  }
} while(index !== -1);
console.log(s);
```

## 3.4、Math对象

Math对象不是构造函数，它具有数学常数和函数的属性和方法，都是以静态成员的方式提供

跟数学相关的运算来找Math中的成员（求绝对值，取整）

[Math](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Global_Objects/Math)

Math 对象并不像 Date 和 String 那样是对象的类，因此没有构造函数 Math()。

```js
Math.PI				返回圆周率（约等于3.14159）。

Math.ceil(x)		返回大于等于其数字参数的最小整数。

Math.floor(x)		返回小于等于其数值参数的最大整数。

Math.round(x)		把数四舍五入为最接近的整数。

Math.random()		返回介于 0 和 1 之间的伪随机数。 注:产生的伪随机数介于 0 和 1 之间（含 0，不含 1），也就是，返回值可能为0，但总是小于1。

Math.max(x,y)		返回 x 和 y 中的最高值。

Math.min(x,y)		返回 x 和 y 中的最低值。

Math.abs(x)			返回x的绝对值		
```

**代码示例:**

```js
// 求10-20之间的随机数
// 随机生成颜色RGB
// 模拟实现max()/min()
```

## 3.5、全局对象

1、parseInt

​      parseInt() 函数可解析一个字符串，并返回一个整数。

2、parseFloat方法

​      parseFloat()函数可解析一个字符串，并返回一个浮点数。

​      该函数指定字符串中的首个字符是否是数字。如果是，则对字符串进行解析，直到到达数字的末端为止，然后以数字返回该数字，而不是作为字符串。

​      如果参数字符串的第一个字符不能被解析成为数字，则 parseFloat 返回 NaN。

3、isNaN()方法

​      定义和用法

​      isNaN(x):函数用于检查其参数是否是非数字值。 参数x是要检测的值

​      如果x是特殊的非数字值NaN（或者能被转换为这样的值），返回的值就是 true。如果 x 是其他值,则返回 false。

​      isNaN()函数可用于判断其参数是否是NaN，该值表示一个非法的数字（比如被 0 除后得到的结果）,如果把NaN与任何值(包括其自身)相比得到的结果均是false，所以要判断某个值是否是NaN，不能使用 == 或 === 运算符。正因为如此，isNaN() 函数是必需的。

​      提示和注释
​      ​      提示：isNaN()函数通常用于检测parseFloat()和parseInt()的结果，以判断它们表示的是否是合法的数字。当然也可以用isNaN()函数来检测算数错误，比如用0作除数的情况。

```html
<script>
    var loginName = parseInt('amigo1121');
    if(isNaN(loginName)) {
        //如果loginName不是数值,执行如下语句
        alert("parseInt('amigo1121')的结果是: " + loginName);
    } else {
        alert("parseInt('amigo1121')的结果是数值!");
    }
</script>
```

URL编码和解码：<https://www.jianshu.com/p/cfd3c8abb2c4>

## 3.6、基本包装类型

为了方便操作简单数据类型，JavaScript还提供了三个特殊的简单类型类型：String/Number/Boolean

```javascript
// 下面代码的问题？
// s1是基本类型，基本类型是没有方法的
var s1 = 'zhangsan';
var s2 = s1.substring(5);

// 当调用s1.substring(5)的时候，先把s1包装成String类型的临时对象，再调用substring方法，最后销毁临时对象, 相当于：
var s1 = new String('zhangsan');
var s2 = s1.substring(5);
s1 = null;
```

```javascript
// 创建基本包装类型的对象
var num = 18;  				//数值，基本类型
var num = Number('18'); 	//类型转换
var num = new Number(18); 	//基本包装类型，对象
// Number和Boolean基本包装类型基本不用，使用的话可能会引起歧义。例如：
var b1 = new Boolean(false);
var b2 = b1 && true;		// 结果是什么
```

<a id="p2-4"></a>
# 课后习题

## part 1

````html
1、在JavaScript中，定义一个函数所使用的关键字：
    A、function  B、Function  C、fun D、method

2、变量从作用域的角度划分，分为两种()。
    A、全局变量  B、局部变量  C、整体变量  D、局域变量

3、在JavaScript函数中，声明一个变量没有用var，则该变量是()。
    A、全局变量  B、局部变量  C、整体变量  D、局域变量

4、下面()语句可以实现退出函数的功能。
    A、break   B、return  C、continue D、switch

5、下面代码的执行结果为().
<script type="text/javascript">
    var max=34;
    function getMax(){
        var max=47;
        document.writeln(max);
    }
    getMax();
    document.write(max);
</script>

6、下面代码的执行结果为().
<script type="text/javascript">
    var max=34;
    function getMax(){
        max=47;
        document.writeln(max);
    }
    getMax();
    document.write(max);
</script>

7、在调用函数时，给参数赋值的数据类型可以是()
     A、string  B、number  C、object   D、boolean

8、编码实现如下业务逻辑：
    1、定义一个函数，函数包含三个参数begin,end,step,其中begin代表数列的初始值、end代表数列的结束值、step表示步长，即数列之间的增长量，比如sum=1+3+5+7+....+99,其中begin=1,end=99,step=2。

    2、函数的返回值是求该数列的和。

9、 下面代码的执行结果为：
    function t(x,y){
        document.write(x*y);
    }
    t(23,12);
    A、语法错误  B、276   C、没有结果  D、23*12
````

## part 2

```html
1、JavaScript中数组元素的数据类型( )。
    A、可以相同 B、可以不相同   C、必须相同 D、必须不相同

2、JavaScript中数组的长度( )。
    A、可变 B、不可变  C、一定变  D、一定不变

3、pop()方法和shift( )方法的区别是什么？

4、下面()方法可以添加数组元素到数组中。
    A、push()  B、splice()  C、pop()   D、sort()

5、下面()方法可以对数组进行排序。
    A、push()  B、splice()  C、pop()   D、sort()

6、slice()方法和splice()有什么不同?

7、( )方法用于颠倒数组中元素的顺序。
    A、reverse()  B、sort()  C、join()  D、split()

8、( )方法可以把数组转化为字符串。
    A、reverse()  B、sort()  C、join()  D、split()
```

## part 3

```html
1、把一个形如’6/13/2011’的字符串转化为日期，则使用Date对象的()方法。
    A、UTC()  B、parse()  C、setTime()  D、getTimezoneOffset()

2、把一个日期转化一个字符串，并且以特定地区格式显示月、日和年，则选用()方法。
    A、toDateString() B、toTimeString() C、toLocaleDateString() D、toLocaleTimeString()

3、下面()方法实现返回本地时间和UTC时间相差的分钟数。
    A、getMilliseconds() B、getMinutes()  C、getDate() D、getTimezoneOffset()

4、如果当前是星期二，则如下代码的值为()。
    var box = new Date();
    alert(box.getDay());
    A、0 B、1  C、2 D、3

5、如果当前是12月份，则如下代码的值为()。
    var box = new Date();
    alert(box.getMonth());
    A、10 B、11  C、12 D、13

6、在页面上编写代码实现显示时间。

7、在页面上编写代码实现显示年月日。

8、在页面上实现按如下格式显示内容:
       XXXX年XX月XX日 XX:XX:XX  星期X
```

## part 4

```html
练习1:
    获取系统当前时间，然后把日期转换为以下格式
    现在时间是:今天是:****年**月**日,现在时间是:上午/下午 HH:mm:ss

练习2:
    有以下身份证号:
        410105199009090001
    说明：前6位是身份和地区编号，7—14位为出生年月日，后4位为个人编号
    请使用字符串解析成以下格式:
    该用户的出生日期是：****年**月**日。

练习3:
	判断一个数是否是素数(又叫质数，只能被1和自身整数的数)

练习四:
    请根据弹出框输入的特定日期格式拆分日期

    如：请输入一个日期格式的字符串（格式如：月/日/年） 如： 11/24/2014
        经过处理得到：****年**月**日

练习五:
    根据输入的年份、产品类型和随机数产生固定资产编号
    即：固定资产编号=年份+0+产品类型+3位随机数
       程序运行流程：请输入年份：  
                  ……  如2014
                  请选择产品类型（1. 台式机 2. 笔记本 3. 其他）：
                  ……  如3
                  生成3位随机数  如310
                  最后显示固定资产编号

    最后显示的结果应该是201403310
    var num = prompt("请输入一个数值:"); //从弹出框输入一个值
    提示：3位随机数按如下方法产生：[100,999]
```


---

<a id="p3"></a>

# 第3篇 · JavaScript BOM编程

---

<a id="p3-1"></a>
# 一、BOM概述

## 1.1、Web API

### 1.1.1、API的概念

​	API（Application Programming Interface，应用程序接口）是一些预先定义的函数，或指软件系统不同组成部分衔接的约定。 用来提供应用程序与开发人员基于某软件或硬件得以访问的一组例程，而又无需访问源码，或理解内部工作机制的细节。

- 任何开发语言都有自己的API
- API的特征输入和输出(I/O)
  - var max =  Math.max(1, 2, 3);
- API的使用方法(console.log('adf'))

### 1.1.2、Web  API的概念

浏览器提供的一套操作浏览器功能和页面元素的API(BOM和DOM)

此处的Web API特指浏览器提供的API(一组方法)，Web API在后面的课程中有其它含义

Web API：https://developer.mozilla.org/zh-CN/docs/Web/API

### 1.1.3、JavaScript组成部分

![](images03_bom/微信截图_20200707211125.png)

**ECMAScript - JavaScript的核心** 

​	定义了JavaScript 的语法规范

​	JavaScript的核心，描述了语言的基本语法和数据类型，ECMAScript是一套标准，定义了一种语言的标准与具体实现无关。

**BOM - 浏览器对象模型**

​	一套操作浏览器功能的API

​	通过BOM可以操作浏览器窗口，比如：弹出框、控制浏览器跳转、获取分辨率等 

**DOM - 文档对象模型**

​	一套操作页面元素的API

​	DOM可以把HTML看做是文档树，通过DOM提供的API可以对树上的节点进行操作

## 1.2、BOM概述

### 1.2.1、什么是BOM

​	BOM是browser object model的缩写，简称浏览器对象模型。

​	**BOM提供了独立于内容而与浏览器窗口进行交互的对象。**

​	由于BOM主要用于管理窗口与窗口之间的通讯，因此其核心对象是window。

​	**BOM由一系列相关的对象构成，并且每个对象都提供了很多方法与属性。**

​	BOM缺乏标准，JavaScript语法的标准化组织是ECMA，DOM的标准化组织是W3C。

​	BOM最初是Netscape浏览器标准的一部分。

### 1.2.2、BOM层次结构

window对象是BOM的顶层(核心)对象，所有对象都是通过它延伸出来的，也可以称为window的子对象。

![1572956482735](images03_bom/1572956482735.png)

### 1.2.3、BOM可以实现的功能

​	BOM提供了一些访问窗口对象的一些方法，我们可以用它来移动窗口位置，改变窗口大小，打开新窗口和关闭窗口，弹出对话框，进行导航以及获取客户的一些信息如：浏览器品牌版本，屏幕分辨率。

​	**但BOM最强大的功能是它提供了一个访问HTML页面的一入口——document对象，以使得我们可以通过这个入口来使用DOM的强大功能！**

<a id="p3-2"></a>
# 二、window对象

## 2.1、window对象的使用

​	window对象是BOM的顶层(核心)对象，所有对象都是通过它延伸出来的，也可以称为window的子对象。

​	**window 对象表示一个浏览器窗口或一个框架**。在客户端 JavaScript 中，Window 对象是全局对象，所有的表达式都在当前的环境中计算。也就是说，要引用当前窗口根本不需要特殊的语法，可以把那个窗口的属性作为全局变量来使用。例如，可以只写document，而不必写 window.document。

​      同样，可以把当前窗口对象的方法当作函数来使用，如只写 alert()，而不必写 Window.alert()。

​      **示例：**

```js
document.write("直接使用document来调用<br>");
window.document.write("使用window来调用document<br>");

// alert("直接调用alert");
// window.alert("window调用alert");

var a = 10;
document.write(window.a);
```

​      也就是说调用window对象的属性或方法可以省略window。

## 2.2、三种弹出框

**1、alert()：显示带有一段消息和一个确认按钮的警告框。**

![1572956755638](images03_bom/1572956755638.png)

```js
// 1、alert()：显示带有一段消息和一个确认按钮的警告框
// 参数: 任意类型的参数,只需要传递一个参数即可 （基本上都是字符串类）
// 无返回值
var alertReturn = alert("Hello"); // 一个方法如果没有返回值,那么就是undefined
console.log(alertReturn);
```

**2、confirm()：显示带有一段消息以及确认按钮和取消按钮的对话框.返回值为布尔值；如果点击确定则返回true,点击取消返回false。**

![1572956781925](images03_bom/1572956781925.png)

```js
 // 2、confirm()：显示带有一段消息以及确认按钮和取消按钮的对话框.返回值为布尔值；如果点击确定则返回true,点击取消返回false。
// 参数: 任意类型的参数,只需要传递一个参数即可 （基本上都是字符串类）
// 布尔类型
var confirmReturn = confirm("是否删除?");
console.log(confirmReturn);
```

**3、prompt()：显示可提示用户输入的对话框。第一个参数是提示,第二个参数是默认值(可选);返回值为输入的值，取消返回null；需要注意的是，返回的输入值是一个string类型的数据。**

![1572956822510](images03_bom/1572956822510.png)

```js
// 3、prompt()：显示带一段消息和用户输入的对话框并且有确定和取消按钮。
// 第一个参数是提示,第二个参数是默认值(可选,输入框的默认值);
// 点击确定,返回值为输入的值，取消返回null；需要注意的是，返回的输入值是一个string类型的数据。
var ageStr = prompt("请输入您的年龄", "只能输入1-99的数值");
var ageStr = prompt("请输入您的年龄(1-99)");
console.log(ageStr);

// 只要输入的不是1-99,则继续输入
while (true) {
    var ageStr = prompt("请输入您的年龄(1-99)");
    // 把输入的转换为数值,判断是否可以转换为数值
    var age = Number(ageStr); // 非数值字符串,NaN;数值字符串直接转换为数值
    if (!isNaN(age) && age >= 1 && age <= 99) {
        console.log("您的年龄是:" + age);
        break;
    }
}
```

## 2.3、窗体控制

**1、open()：打开一个窗体**

​	语法:window.open(URL,name,[specs]),该方法返回打开窗口的引用

​	参数介绍:

​		URL      可选。打开指定的页面的URL。如果没有指定URL，打开与新的空白窗口

​		name      可选。指定窗口的名称。

​		specs      一个逗号分隔的项目列表。支持以下值：

​			height=pixels      窗口的高度。最小.值为100

​                        left=pixels​      该窗口距离屏幕左侧的位置

​                        top=pixels​      该窗口距离屏幕顶部的位置

​                        width=pixels​      窗口的宽度.最小.值为100

注:窗口相对位置是以屏幕为基准。

```html
<script>
    window.open("page.html","newWind","width=520,height=420,left=100,top=30")
</script>
```

**2、close()：关闭浏览器窗口。**

**3、moveBy()：可相对窗口的当前坐标把它移动指定的像素。**

​	window.moveBy(x,y)

​		x      要把窗口在x轴移动的像素数,可以是正、负数值。

​		y      要把窗口在y轴移动的像素数,可以是正、负数值。

**4、moveTo()：把窗口的左上角移动到一个指定的坐标。**

​	window.moveTo(x,y)

​		x      窗口新位置的 x 坐标,可以是正、负数值。

​		y      窗口新位置的 y 坐标,可以是正、负数值。

**5、resizeTo()：把窗口的大小调整到指定的宽度和高度。**

​	resizeTo(width,height)
​		width      必需。想要调整到的窗口的宽度。以像素计。

​		height     可选。想要调整到的窗口的高度。以像素计。

​	注: 有最小值

**6、resizeBy()：按照指定的像素调整窗口的大小。**

​	resizeBy(width,height)

​		width      必需。要使窗口宽度增加的像素数。可以是正、负数值。

​		height     可选。要使窗口高度增加的像素数。可以是正、负数值。

​      注: 有最小值

**7、focus()：把键盘焦点给予一个窗口。可确保新的窗口得到焦点。**

跨域问题解决方法：<https://blog.csdn.net/farmwang/article/details/79850818>

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <button id="btn1">打开一个新窗口</button>
    <button id="btn2">关闭新窗口</button>
    <button id="btn3">逐次移动新窗口位置</button>
    <button id="btn4">直接设置新窗口位置</button>
    <button id="btn5">逐次改变新窗口大小</button>
    <button id="btn6">直接设置新窗口大小</button>
    <button id="btn7">获取窗口名称</button>

    <script>
        var btn1 = document.getElementById("btn1");
        var btn2 = document.getElementById("btn2");
        var btn3 = document.getElementById("btn3");
        var btn4 = document.getElementById("btn4");
        var btn5 = document.getElementById("btn5");
        var btn6 = document.getElementById("btn6");
        var btn7 = document.getElementById("btn7");

        var newWindow; // 没有赋值是undefined

        // 当点击按钮1的时候,打开新窗口
        btn1.onclick = function () {
            // open(URL,name,spacs)：打开一个窗体
            // URL:可以是一个页面或一张图片
            // name: 给新创建指定名称
            // spacs：相关窗口配置 width、height、left、top
            // 所谓的左侧和右侧都是基于电脑屏幕
            // 这三个参数都是字符串类型
            // open方法返回一个window对象的引用
            newWindow = open("images/1.jpg", "newWindow", "width=300,height=200,left=100,top=100");
            // console.log(newWindow.innerHeight)
            // console.log(newWindow.outerHeight);
        }

        btn2.onclick = function () {
            // console.log(newWindow);
            // close()：关闭浏览器窗口
            if (newWindow) { // undefined -> false   
                newWindow.close();
            }

            // console.log(newWindow.closed);
        }

        // 点击btn3,报错:Blocked a frame with origin "null" from accessing a cross-origin frame.
        // 跨域不允许你js操作另外一二窗口
        // file:///D:/VSCode_workspace/0715/03_%E7%AA%97%E4%BD%93%E6%8E%A7%E5%88%B6.html
        btn3.onclick = function () {
            // moveBy()：可相对窗口的当前坐标把它移动指定的像素。
            // x  要把窗口右移的像素数,可以是正、负数值。
            // y  要把窗口下移的像素数,可以是正、负数值。
            if (newWindow) {
                newWindow.moveBy(10, 10);
                newWindow.focus();
            }
        }

        // 同源策略: 
        // 协议  ip地址  端口号  资源路径
        // 安装Live Server插件,基于协议访问页面


        btn4.onclick = function () {
            // moveTo()：把窗口的左上角移动到一个指定的坐标
            // x  要把窗口右移的像素数,可以是正、负数值。
            // y  要把窗口下移的像素数,可以是正、负数值。
            if (newWindow) {
                newWindow.moveTo(10, 10);
                newWindow.focus();
            }
        }

        btn5.onclick = function () {
            // resizeBy()：按照指定的像素调整窗口的大小
            // width 必需。 要使窗口宽度增加的像素数。 可以是正、 负数值。
            // height 可选。 要使窗口高度增加的像素数。 可以是正、 负数值。
            if (newWindow) {
                newWindow.resizeBy(10, 10);
                newWindow.focus();
            }
        }

        btn6.onclick = function () {
            // resizeTo()：把窗口的大小调整到指定的宽度和高度
            // width 必需。 要使窗口宽度增加的像素数。 可以是正、 负数值。
            // height 可选。 要使窗口高度增加的像素数。 可以是正、 负数值。
            if (newWindow) {
                newWindow.resizeTo(400, 400);
                newWindow.focus();
            }
        }

        btn7.onclick = function () {
            console.log(newWindow.name);
        }
    </script>
</body>

</html>
```

## 2.4、窗体滚动

**1、scrollBy(xnum,ynum)：按照指定的像素值来滚动内容。**

​	xnum      把文档向右滚动的像素数。

​	ynum      把文档向下滚动的像素数。

**2、scrollTo(xpos,ypos)：把内容滚动到指定的坐标。**

​	xpos      要在窗口文档显示区左上角显示的文档的 x 坐标。

​	ypos      要在窗口文档显示区左上角显示的文档的 y 坐标。

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        body {
            width: 1600px;
        }

        div {
            width: 300px;
            border: 1px solid black;
            background: red;
            position: fixed;
            right: 0;
            top: 100px;
        }
    </style>
</head>

<body>
    <div>
        <button id="btn1">scrollBy逐次滚动内容</button>
        <button id="btn2">scrollTo直接滚到指定位置</button>
        <button id="btn3">打印当前窗口内容</button>
    </div>
    <script>
        var btn1 = document.getElementById("btn1");
        var btn2 = document.getElementById("btn2");
        var btn3 = document.getElementById("btn3");

        btn1.onclick = function () {
            scrollBy(10, 10);
        }

        btn2.onclick = function () {
            scrollTo(0, 0)
        }

        btn3.onclick = function () {
            // console.log("点击了按钮");
            print();
        }
    </script>
    <hr>
    <p>1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 </p>
    ....
</body>

</html>
```

## 2.5、窗体打印

**print()：打印当前窗口的内容。**

​	调用 print() 方法所引发的行为就像用户单击浏览器的打印按钮。通常，这会产生一个对话框，让用户可以取消或定制打印请求。

![1572957270150](images03_bom/1572957270150.png)

## 2.6、定时器(重点)

window对象中处理时间和间隔的函数有4个：

​	setTimeout()函数、clearTimeout()函数

​	setInterval()函数、clearInterval()函数

### 2.6.1、延时型定时器

![1572957377729](images03_bom/1572957377729.png)

​	setTimeout()：定义延时定时器,在指定的时间后调用函数

​	**语法：**

​		setTimeout(fun,time);

​	其中参数fun：函数体或函数名;time指定时间，单位为毫秒。其返回值有一个id,代表当前的这个setTimeout()函数。

​	clearTimeout(id)：清除延时定时器,取消指定id的setTimeout函数。

 **示范代码：**

```js
setTimeout(function () {
    document.write("隔3秒后触发");
}, 3000)    //在3秒后输出

setTimeout(fun1, 5000);     //在5秒后输出

function fun1() {
    document.write("函数名的方式5秒后触发");
}
```

### 2.6.2、间隔型定时器

​	setInterval()：定义间隔型定时器,在间隔指定的事件后重复调用函数。

​	**语法：**
​		setInterval(fun1,time)　　

​	fun：函数体或函数名，time指定的时间，单位为毫秒。会返回一个值id。

​	clearInterval(id)：清除间隔型定时器

​	参数id是setInterval()函数返回的值，根据这个值可以停止返回值为idsetInterval()的执行。

**示范代码：**

```js
var h = setInterval(function () {
    document.write("3秒输出一次<br/>");
}, 3000);
```

注意，JavaScript是单线程的，因此，这个定时函数实际上是通过插入执行队列的方式来实现。

### 2.6.3、案例

**动态时间案例1：**

​      由于涉及到时间的显示问题，所以要用到日期对象Date，还有时间在不停地走，因此需要不断地调用函数，所以要用到Windows的定时器setInterval( )方法。

```html
<script>
    function disptime(){
        var today = new Date(); //获得当前时间
        var hh = today.getHours();  //获得小时、分钟、秒
        var mm = today.getMinutes();
        var ss = today.getSeconds();
        document.getElementById("myclock").innerHTML=hh+":"+mm+":"+ss;
    }
    window.setInterval(disptime,1000);
</script>
```

**动态时间案例2：**

```html
<!-- 这个div用来显示动态时间 -->
<div id="timeDiv">
    <!-- 我们不能给这个div里面写内容,因为时间是不固定,需要通过JS来设置 -->
</div>

<script>
    //给页面元素设置文本内容,那么肯定要获取到元素节点,然后通过元素节点.innerText来设置文本内容

    //获取到timeDiv元素节点
    var timeDiv = document.getElementById("timeDiv");

    //这个函数是用来给timeDiv设置字符串
    function setTimeStr() {
        //获取到系统时间,然后给其设置内容
        var time = new Date();

        //获取到年月日
        var year = time.getFullYear();
        var month = time.getMonth()+1;
        var date = time.getDate();

        //获取时分秒
        var hour = time.getHours();

        //ampStr用来表示上午或下午
        var apmStr = hour >= 12 ?  "下午" : "上午";

        var minute = time.getMinutes();
        var second = time.getSeconds();

        timeDiv.innerText = "今天是:"+year+"年"+getTwo(month)+"月"+getTwo(date)+"日,现在时间是:"+apmStr+" "
            +getTwo(hour)+":"+getTwo(minute)+":"+getTwo(second);
    }

    //让timeDiv里面的内容,每一秒改变一次
    setInterval(setTimeStr,1000);

    //为了解决第一秒没有显示时间的小bug,可以提前调用一次
    setTimeStr();

    //月日时分秒可能是个位数,那么如果是个位数,我们需要对齐进行格式化处理
    //如果小于10,那么给其拼字符串"0"
    function getTwo(t){ //t表示形参,回头可以把月 日 时分秒作为实参传递进来进行处理
        return t < 10 ? "0"+t : t;
    }

</script>
```

**图片时间案例：**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document</title>
</head>

<body>
  <div id="imgClock">

  </div>
  <script>
    var imgClock = document.getElementById("imgClock");

    function handleTime() {
      imgClock.innerHTML = "";
      var date = new Date();
      var hours = date.getHours();
      var minutes = date.getMinutes();
      var seconds = date.getSeconds();
      changeImg(hours);
      changeColon();
      changeImg(minutes);
      changeColon();
      changeImg(seconds);
    }

    // 处理数值
    function changeImg(num) {
      var imgEle1 = document.createElement("img");
      var imgEle2 = document.createElement("img");
      if (num < 10) {
        imgEle1.src = "images/0.png";
        imgEle2.src = "images/" + num + ".png";
      } else {
        var num1 = parseInt(num / 10);
        var num2 = num % 10;
        imgEle1.src = "images/" + num1 + ".png";
        imgEle2.src = "images/" + num2 + ".png";
      }
      imgClock.appendChild(imgEle1);
      imgClock.appendChild(imgEle2);
    }

    // 处理冒号
    function changeColon() {
      var colonImg = document.createElement("img");
      colonImg.src = "images/10.png";
      imgClock.appendChild(colonImg);
    }

    // 先调用一次
    handleTime();
    setInterval(handleTime, 1000);
  </script>
</body>

</html>
```

**简易轮播图案例：**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        .slideDiv {
            border: 1px solid black;
            width: 640px;
            height: 400px;
        }

        .slideDiv>img {
            width: 640px;
        }
    </style>
</head>

<body>
    <!-- 
        轮播图:
            图片切换轮播    京东
            滑动轮播        淘宝
     -->
    <div id="slideDiv" class="slideDiv">
        <img src="images/1.jpg" alt="" id="slideImg">
    </div>

    <script>
        // 每隔3s中切换另外一张图片
        // 1.jpg  2.jpg  3.jpg  4.jpg  ->1.jpg
        var slideImg = document.getElementById("slideImg");

        // 图片编号
        var imgNum = 1;

        setInterval(function () {
            if (imgNum == 4) {
                imgNum = 1;
            } else {
                imgNum++;
            }
            console.log(imgNum)
            // 修改img的src属性
            slideImg.src = "images/" + imgNum + ".jpg";
        }, 3000)
    </script>
</body>

</html>
```

## 2.7、window对象常用属性(重点)

​	innerWidth      返回窗口的文档显示区的宽度。

​	innerHeight     返回窗口的文档显示区的高度。

​	name      ​      设置或返回窗口的名称。

​	outerheight     返回窗口的外部高度。

​	outerwidth      返回窗口的外部宽度。

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <script>
        document.write("窗口文档显示区域的宽度:" + innerWidth + "<br>");
        document.write("窗口文档显示区域的高度:" + innerHeight + "<br>");

        document.write("窗口的宽度:" + outerWidth + "<br>");
        document.write("窗口的高度:" + outerHeight + "<br>");
    </script>
</body>

</html>
```

<a id="p3-3"></a>
# 三、History对象

​	History 对象包含用户（在浏览器窗口中）访问过的 URL。

​	History 对象是 window 对象的一部分，可通过 window.history 属性对其进行访问。

## 3.1、History对象属性

| 属性   | 说明                           |
| ------ | ------------------------------ |
| length | 返回当前窗口历史列表中的网址数 |

## 3.2、History对象方法

| 方法      | 说明                              |
| --------- | --------------------------------- |
| back()    | 加载 history 列表中的前一个 URL   |
| forward() | 加载 history 列表中的下一个 URL   |
| go(num)   | 加载 history 列表中的某个具体页面 |

History对象：back() 方法

​	back() 方法可加载历史列表中的前一个 URL（如果存在）。

​	调用该方法的效果等价于点击后退按钮或调用 history.go(-1)。

History对象：forward() 方法

​	forward() 方法可加载历史列表中的下一个 URL。

​	调用该方法的效果等价于点击前进按钮或调用 history.go(1)。

History对象：go() 方法

​	go() 方法可加载历史列表中的某个具体的页面。

​	该参数可以是数字，使用的是要访问的 URL 在 History 的 URL 列表中的相对位置。（-1上一个页面，1前进一个页面)。或一个字符串，字符串必须是局部或完整的URL，该函数会去匹配字符串的第一个URL。

​	history.go(number|URL)

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <a href="春.html">春</a>
    <a href="夏.html">夏</a>
    <a href="秋.html">秋</a>
    <a href="冬.html">冬</a>
    <hr>
    <h1>这里是春天页面</h1>

    <hr>
    <button id="btn1">后退</button>
    <button id="btn2">前进</button>

    <script>
        var btn1 = document.getElementById("btn1");
        var btn2 = document.getElementById("btn2");
        btn1.onclick = function () {
            history.back();
        }

        btn2.onclick = function () {
            history.forward();
        }
    </script>
</body>

</html>
```

<a id="p3-4"></a>
# 四、Location 对象

​	Location 对象包含有关当前 URL 的信息。

​	Location 对象是 window 对象的一部分，可通过 window.location 属性对其进行访问。

## 4.1、Location对象属性

| 属性     | 描述                          |
| -------- | ----------------------------- |
| hash     | 返回一个URL的锚部分(锚点)     |
| host     | 返回一个URL的主机名和端口     |
| hostname | 返回URL的主机名               |
| href     | 返回完整的URL                 |
| pathname | 返回的URL路径名。             |
| port     | 返回一个URL服务器使用的端口号 |
| protocol | 返回一个URL协议               |
| search   | 返回一个URL的查询部分 ？之后  |

## 4.2、Location对象方法

| 方法      | 说明                                              |
| --------- | ------------------------------------------------- |
| assign()  | 载入一个新的文档    location.assign(URL)          |
| reload()  | 重新载入当前文档    location.reload();            |
| replace() | 用新的文档替换当前文档   location.replace(newURL) |

​      window.location.assign(url) ： 加载 URL 指定的新的 HTML 文档。就相当于一个链接，跳转到指定的url，当前页面会转为新页面内容，可以点击后退返回上一个页面。

​      window.location.replace(url) ： 通过加载 URL 指定的文档来替换当前文档，这个方法是替换当前窗口页面，前后两个页面共用一个窗口，没有后退返回上一页的

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <button id="btn1">assign载入一个新的文档</button>
    <button id="btn2">reload重新加载文档</button>
    <button id="btn3">replace替换当前文档</button>
    <script>
        // http://127.0.0.1:5500/0715/10_location%E5%AF%B9%E8%B1%A1.html?userName=zhangsan&&userPwd=123#abc
        // url: 协议://ip地址:端口号/资源路径?请求内容(搜索内容)#锚链接

        console.log("完整的URL地址:" + location.href);
        console.log("协议:" + location.protocol);
        console.log("ip地址和端口号:" + location.host);
        console.log("ip地址:" + location.hostname)
        console.log("端口号:" + location.port);
        console.log("完整资源路径:" + location.pathname);
        console.log("搜索内容:" + location.search);
        console.log("锚部分:" + location.hash);

        var btn1 = document.getElementById("btn1");
        var btn2 = document.getElementById("btn2");
        var btn3 = document.getElementById("btn3");

        btn1.onclick = function () {
            location.assign("http://www.baidu.com");
        }

        btn2.onclick = function () {
            location.reload();
        }

        btn3.onclick = function () {
            location.replace("http://www.baidu.com");
        }
    </script>
</body>

</html>
```

<a id="p3-5"></a>
# 五、Screen 对象

Screen 对象包含有关客户端显示屏幕的信息。

| 属性        | 说明                                     |
| ----------- | ---------------------------------------- |
| availHeight | 返回屏幕的高度（不包括Windows任务栏）    |
| availWidth  | 返回屏幕的宽度（不包括Windows任务栏）    |
| colorDepth  | 返回目标设备或缓冲器上的调色板的比特深度 |
| height      | 返回屏幕的总高度                         |
| pixelDepth  | 返回屏幕的颜色分辨率（每像素的位数）     |
| width       | 返回屏幕的总宽度                         |

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>

    <script>
        console.log("不包含任务栏的屏幕高度:" + screen.availHeight);
        console.log("不包含任务栏的屏幕宽度:" + screen.availWidth);

        console.log("屏幕高度:" + screen.height);
        console.log("屏幕宽度:" + screen.width);
    </script>
</body>

</html>
```

<a id="p3-6"></a>
# 六、Navigator 对象

Navigator 对象包含有关浏览器的信息。

| 属性          | 说明                                                         |
| ------------- | ------------------------------------------------------------ |
| appCodeName   | 返回浏览器的代码名appCodeName 属性是一个只读字符串，声明了浏览器的代码名。在所有以 Netscape 代码为基础的浏览器中，它的值是 "Mozilla"。为了兼容起见，在 Microsoft 的浏览器中，它的值也是 "Mozilla"。 |
| appName       | 返回浏览器的名称                                             |
| appVersion    | 返回浏览器的平台和版本信息                                   |
| cookieEnabled | 返回指明浏览器中是否启用 cookie 的布尔值                     |
| platform      | 返回运行浏览器的操作系统平台                                 |
| userAgent     | 返回由客户机发送服务器的user-agent 头部的值                  |

**说明：**

​	1.navigator.appCodeName：IE/Firefox/Chrome 系列浏览器中，它的值都是 "Mozilla"。

​	2.navigator.appName：IE/Firefox/Chrome 系列浏览器中 均为 Netscape。

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>

    <iframe src=""></iframe>
    <iframe src=""></iframe>
    <iframe src=""></iframe>

    <script>
        console.log("appCodeName:" + navigator.appCodeName); // 都是Mozilla
        console.log("appName:" + navigator.appName) // 都是Netscape
        console.log("appVersion:" + navigator.appVersion);
        console.log("cookieEnabled:" + navigator.cookieEnabled);
        console.log("platform:" + navigator.platform)
        console.log("userAgent:" + navigator.userAgent)

    </script>
</body>

</html>
```

<a id="p3-7"></a>
# 七、Frames对象

frames 属性返回窗口中所有命名的框架。

该集合是 Window 对象的数组，每个 Window 对象在窗口中含有一个框架或 ```<iframe>```。属性 frames.length 存放数组 frames[] 中含有的元素个数。注意，frames[] 数组中引用的框架可能还包括框架，它们自己也具有 frames[] 数组。


---

<a id="p4"></a>

# 第4篇 · JavaScript DOM编程（基础篇）

---

<a id="p4-1"></a>
# 一、JavaScript DOM 概述

## 1.1、DOM概念

​	文档对象模型（Document Object Model，简称DOM），是W3C组织推荐的处理超文本标记语言的标准编程接口。它是一种与平台和语言无关的应用程序接口(API),它可以动态地访问程序和脚本,更新其内容、结构和www文档的风格(目前,HTML和XML文档是通过说明部分定义的)。文档可以进一步被处理，处理的结果可以加入到当前的页面。DOM是一种基于树的API文档，它要求在处理过程中整个文档都表示在存储器中。

​	DOM(Document Object Model)即文档对象模型，针对HTML和XML文档的API(应用程序接口)。

​	DOM描绘了一个层次化的节点树，可以添加、移除和修改页面的内容。

​	Document用于表现HTML页面当前窗体的内容,document对象包含一个节点对象，此对象包含每个单独页面的所有HTML元素，这就是W3C的DOM对象。

​        通过 JavaScript，您可以重构整个HTML文档。您可以添加、移除、改变或重排页面上的项目。要改变页面的某个东西，JavaScript就需要对HTML文档中所有元素进行访问的入口。这个入口，连同对HTML 元素进行添加、移动、改变或移除的方法和属性，都是通过文档对象模型来获得的（DOM）。

​        在 1998 年，W3C 发布了第一级的 DOM 规范。这个规范允许访问和操作 HTML 页面中的每一个单独的元素。所有的浏览器都执行了这个标准，因此，DOM 的兼容性问题也几乎难觅踪影了。DOM 可被 JavaScript 用来读取、改变 HTML、XHTML 以及 XML 文档。

## 1.2、DOM的作用

通过可编程的对象模型，JavaScript 获得了足够的能力来创建“动态的 HTML”。

>JavaScript 能够改变页面中的所有 HTML 元素
>
>JavaScript 能够改变页面中的所有 HTML 属性
>
>JavaScript 能够改变页面中的所有 CSS 样式
>
>JavaScript 能够对页面中的所有事件做出反应

**静态页面和动态页面:**

​	静态页面，即静态网页，是实际存在的，无需经过服务器的编译，直接加载到客户浏览器上显示出来。静态网页，随着html代码的生成，页面的内容和显示效果就基本上不会发生变化了——除非你修改页面代码。常见的静态页面举例：.html扩展名的、.htm扩展名的。

​	所谓的动态网页，是指跟静态网页相对的一种网页编程技术。动态网页，页面代码虽然没有变，但是显示的内容却是可以随着时间、环境或者数据库操作的结果而发生改变的。

​	值得强调的是，不要将动态网页和页面内容是否有动感混为一谈。这里说的动态网页，与网页上的各种动画、滚动字幕等视觉上的动态效果没有直接关系，动态网页也可以是纯文字内容的，也可以是包含各种动画的内容，这些只是网页具体内容的表现形式，无论网页是否具有动态效果，只要是采用了动态网站技术生成的网页都可以称为动态网页。

​	我们现在学习JS写的动画效果,不叫动态页面,只能称之为静态页面的动态效果;

​	总之，动态网页是基本的html语法规范与Java、VB、VC等高级程序设计语言、数据库编程等多种技术的融合，以期实现对网站内容和风格的高效、动态和交互式的管理。因此，从这个意义上来讲，凡是结合了HTML以外的高级程序设计语言和数据库技术进行的网页编程技术生成的网页都是动态网页。 

## 1.3、DOM总结

![1573034437922](images04_dom/1573034437922.png)

**每个载入浏览器的 HTML 文档都会成为 Document 对象**。

​	Document 对象使我们可以从脚本中对 HTML 页面中的所有元素进行访问。
​	Document 对象是 Window 对象的一部分。

**当浏览器打开一个HTML文档时，浏览器解析HTML文档的标签，并创建表示这些标签的对象，这些对象就是HTML文档对象(标签元素对象)**。

​	文档对象即Document 对象，指的是一回事。

<a id="p4-2"></a>
# 二、JavaScript节点与节点树

​        当浏览器加载html页面的时候,会生成一个与之对应的Document对象。Dcoument对象又称之为文档对象;

​        节点树: 加载HTML 页面时，Web 浏览器生成一个与之对应的树型结构，用来表示页面内部结构。DOM 将这种树型结构理解为由节点组成。

​        下面这个图片表示一个文档树（节点树）：

![1573034494925](images04_dom/1573034494925.png)

​        从上图的树型结构，我们理解几个概念，html 标签没有父辈，没有兄弟，所以html 标签为根标签。head 标签是html子标签，meta 和title标签之间是兄弟关系。

​        如果把每个标签当作一个节点的话，那么这些节点组合成了一棵节点树。经常把标签称作为元素，是同一个意思。

​        常用节点分为三类：元素节点、文本节点、属性节点。

![1573034534818](images04_dom/1573034534818.png)

根据 DOM，HTML 文档中的每个成分都是一个节点。

DOM 是这样规定的：

> 整个文档是一个文档节点。
>
> 每个 HTML 标签是一个元素节点。
>
> 包含在 HTML 元素中的文本是文本节点。
>
> 每一个 HTML 属性是一个属性节点。
>
> 注释属于注释节点。

<a id="p4-3"></a>
# 三、JavaScript获取HTML标签元素

​	W3C提供了比较方便简单的定位节点的方法，以便我们快速的对节点进行操作，分别为：getElementById()、getElementsByClassName()、getElementsByName()、getElementsByTagName()、getElementsByTagNameNS()，其中常用的是下面五个方法。

## 3.1、常用方法介绍

> getElementById()​        返回对拥有指定 id 的第一个对象的引用,返回值Element。
>
> getElementsByName()​        返回带有指定名称的对象集合。返回值NodeList/HTMLCollection。
>
> getElementsByTagName()​        返回带有指定标签名的对象集合。返回值NodeList/HTMLCollection。
>
> getElementsByClassName()​        返回所有指定类名的对象集合。返回值NodeList/HTMLCollection。
>
> querySelector()				返回文档中匹配指定 CSS 选择器的一个元素。
>
> querySelectorAll()			返回文档中匹配指定 CSS 选择器的所有元素。

### 3.1.1、根据id获取元素

**getElementById()方法**：

​	元素id属性表示一个元素节点的唯一性，不能同时给两个或以上的元素节点创建同一个命名的id。

​	getElementById()方法，接受一个参数：获取元素的id。如果找到相应的元素则返回该元素,如果不存在,则返回null。

```js
// 比如获取id 为box 的元素节点：
var box = document.getElementById('box');

//获取到的数据类型 HTMLDivElement，对象都是有类型的
```

​	当我们通过getElementById()获取到特定元素节点时，访问它的一系列属性。

​	注意：由于id名具有唯一性，部分浏览器支持直接使用id名访问元素，但不是标准方式，不推荐使用。

### 3.1.2、根据name获取元素

**getElementsByName()方法**

​        元素name属性表示一个元素节点的名字，在同一个网页上，该属性并不要求唯一性，相同的name可以出现在多个标签上。

​        getElementsByName()方法可以获取相同名称(name)的元素，返回一个元素节点列表。

​        可以通过下标来访问列表里面的元素。

**示例:**

```js
document.getElementsByName('goods') //获取属性name的值为goods的所有元素

document.getElementsByName('goods')[0]//获取属性name的值为goods的第一个元素

document.getElementsByName('goods')[1]//获取属性name的值为goods的第二个元素

// 根据所有的爱好复选框
var inputs = document.getElementsByName('hobby');
for (var i = 0; i < inputs.length; i++) {
  var input = inputs[i];
  console.log(input);
}
```

### 3.1.3、根据标签名获取元素

**getElementsByTagName()方法**

​        getElementsByTagName()方法将返回一个元素节点对象，这个对象保存着所有相同元素名的节点列表。

**示例:**

```js
document.getElementsByTagName('*'); //获取所有元素

document.getElementsByTagName('li'); //获取所有li 元素

document.getElementsByTagName('li')[0]; //获取第一个li元素

document.getElementsByTagName('li').length; //获取所有li元素的数目

// 获取所有div元素
var divs = document.getElementsByTagName('div');
// 遍历
for (var i = 0; i < divs.length; i++) {
  var div = divs[i];
  console.log(div);
} 
```

​	注:NodeList不仅可以通过下标访问指定标签元素,还可以通过length属性来查询列表节点数量.

​	**重点: 该方法不仅可以通过document对象调用,还可以通过元素节点Element来访问**

### 3.1.4、根据类名获取元素

**getElementsByClassName()方法**

​        getElementsByClassName()方法返回文档中所有指定类名的元素集合，作为 NodeList 对象。参数为String,需要获取的元素类名,多个类名使用空格分隔(尽量不用);

**示范代码1:**

```js
//获取包含 "example" 和 "color" 类名的所有元素:
var x = document.getElementsByClassName("example color");
```

**示范代码2:**

```js
//查看文档中有多少个样式class="example"的元素(使用 NodeList 对的 length 属性):
var x = document.getElementsByClassName("example").length;
```

### 3.1.5、根据选择器获取元素

​	querySelector()方法返回文档中匹配指定 CSS 选择器的一个元素。

​	**注意：** querySelector() 方法仅仅返回匹配指定选择器的第一个元素。如果你需要返回所有的元素，请使用 querySelectorAll() 方法替代。

```js
// 获取页面中id为text的元素
var text = document.querySelector('#text');
console.log(text);

// 获取页面中所有class为box的元素
var boxes = document.querySelectorAll('.box');
for (var i = 0; i < boxes.length; i++) {
  var box = boxes[i];
  console.log(box);
}
```

**深入解析document.write():**

​	write()        向文档写 HTML 表达式 或 JavaScript 代码。

​        温馨提示：文档加载之后使用docunment.write()会覆盖原文档.

​        	除了直接输出文字外，它还支持带有HTML标签的输出内容。
​        	比如直接输出一个标题
​        	比如在输出内容中加入br换行标签
​        	比如直接输出列表项......

​        **注意事项:绝对不要在文档加载完成之后使用 document.write()。这会覆盖该文档。**

### 3.1.6、封装函数获取元素

```js
function my$(id) {
  return document.getElementById(id);
}
```

## 3.2、Element和NodeList

​        在 HTML DOM 中，Element 对象表示 HTML 元素。

​        Element 对象可以拥有类型为元素节点、文本节点、注释节点的子节点。

​        NodeList 对象表示节点列表，比如 HTML 元素的子节点集合。

​        我们可通过节点列表中的节点索引号来访问列表中的节点（索引号由0开始）。

​        节点列表可保持其自身的更新。如果节点列表或 XML 文档中的某个元素被删除或添加，列表也会被自动更新。

<a id="p4-4"></a>
# 四、JavaScript操作标签内容

![1573034825065](images04_dom/1573034825065.png)

​        element.innerHTML​        设置或返回元素的内容。

​		注:可以设置内容的时候加上标签，设置的标签会被浏览器解析

​        element.innerText​        设置或返回元素的文本内容

​        element.tagName​        返回元素的标签名。

```js
var box = document.getElementById('box');

box.innerHTML = '我是文本<p>我会生成为标签</p>';

console.log(box.innerHTML);

box.innerText = '我是文本<p>我不会生成为标签</p>';

console.log(box.innerText);
```

**innerText和innerHTML的区别:**

​        innerText只能获取到文本内容,标签不会被获取; innerHTML获取到所有的内容,包含标签;

​        innerText设置的内容会被浏览器认为是纯文本;innerHTML设置的内容会被浏览器认为是HTML文本,如果存在标签会被解析;

**innerText浏览器兼容问题**

```html
<div id="box">
    我是一个box
    <b>hello</b>
</div>
<script>
    // innerText  最早出现在IE浏览器中
    // 浏览器兼容问题
    
    // 老版本的firefox浏览器不支持innerText
    // 2016的时候 已经把innerText 在DOM中规定为正式的标准属性
   
    // textContent

    var box = document.getElementById('box');
    // 都会把标签过滤
    // 前后的空白和一些换行去掉
    console.log(box.innerText);
    // 原封不动的把内容输出
    console.log(box.textContent);
</script>
```

```html
<div id="box">
    hello
</div>
<script>
    // 如何知道。浏览器是否支持元素的某个属性
    var box = document.getElementById('box');

    // 当属性不存在的时候返回的是  undefined
    console.log(typeof box.a);
    // 当属性存在的时候返回的是 该属性的类型
    console.log(typeof box.id);


    var box = document.getElementById('box');
    console.log(getInnerText(box));

    // 处理innerText的兼容性问题
    function getInnerText(element) {
        // 判断当前浏览器 是否支持元素的innerText属性，支持innerText 使用element.innerText获取内容
        // 如果不支持innerText属性，使用element.textContent获取内容

        if (typeof element.innerText === 'string') {
            return element.innerText;
        } else {
            return element.textContent;
        }
    }

    // box.innerHTML = 'hello world';

    // 设置内容的时候
    // innerText(textContent)       当设置不含标签的内容的时候应该使用innerText，效率高
    // innerHTML 
</script>
```

<a id="p4-5"></a>
# 五、JavaScript操作标签属性

## 5.1、HTML基本属性操作

​        element.属性名​        设置或返回元素的指定属性。

​        element.className​        设置或返回元素的 class 属性。

```js
var link = document.getElementById('link');
console.log(link.href);
console.log(link.title);

var pic = document.getElementById('pic');
console.log(pic.src);
```

​        注:class属性的操作必须使用className

​        注:Element对象使用 . 可以调用对象的各个属性

​	注:当html中的标签的属性，只有一个值的时候,DOM中对应的元素的属性值是布尔类型

## 5.2、HTML方法操作属性

**element.getAttribute()​        返回元素节点的指定属性值。**

​        getAttribute()方法将获取元素中某个属性的值。它和直接使用.属性获取属性值的方法有一定区别。

```js
document.getElementById('box').getAttribute('id');//获取元素的id 值
document.getElementById('box').id; //获取元素的id 值
document.getElementById('box').getAttribute('mydiv');//获取元素的自定义属性值
document.getElementById('box').mydiv //获取元素的自定义属性值，非IE 不支持
document.getElementById('box').getAttribute('class');//获取元素的class 值
```

**element.setAttribute()​        把指定属性设置或更改为指定值**
​        setAttribute()方法将设置元素中某个属性和值。它需要接受两个参数：属性名和值。如果属性本身已存在，那么就会被覆盖。

```js
document.getElementById('box').setAttribute('align','center');//设置属性和值
document.getElementById('box').setAttribute('bbb','ccc');//设置自定义的属性和值
```

**element.removeAttribute()        从元素中移除指定属性。**
​        removeAttribute()可以移除HTML 属性。

```js
document.getElementById('box').removeAttribute('style');//移除属性
```

注:使用属性只能来获取和设置的是元素对象原始属性;使用方法可以用来设置元素对象自定义的属性;

## 5.3、案例

### 5.3.1、点击按钮切换图片

```html
<input type="button" value="点我" id="btn">
<br>
<img src="images/a.jpg" id="mv" alt="" width="400" height="300">

<script>
    // 1 获取元素
    var btn = document.getElementById('btn');
    var mv = document.getElementById('mv');
    // 2 给按钮注册事件
    var flag = 1;  // 当flag的值是1 的时候 对应a.jpg   当flag的值是2的时候 对应 b.jpg
    btn.onclick = function () {
        // 3 切换图片
        if (flag === 1) {
            mv.src = 'images/b.jpg';
            flag = 2;
        } else if (flag === 2) {
            mv.src = 'images/a.jpg';
            flag = 1;
        }
    }
</script>
```

### 5.3.2、点击按钮显示隐藏div

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    #box {
      background-color: red;
      width: 200px;
      height: 200px;
    }

    .show {
      display: block;
    }

    .hidden {
      display: none;
    }
  </style>
</head>
<body>
   <input type="button" id="btn" value="隐藏">
   <br>
   <div id="box" >
     
   </div>
  <script>
    //1 获取元素
    var btn = document.getElementById('btn');
    //2 给按钮注册事件
    // isShow记录了box的状态，true 显示 ，false 隐藏
    var isShow = true;
    btn.onclick = function () {
      //3 控制div的显示隐藏
      var box = document.getElementById('box');
      if (isShow) {
        // 为什么DOM对象的对应的标签的class属性的名字叫做className ，应为class 在js中是关键字
        // 关键字不可以作为变量或者属性的名字
        box.className = 'hidden';

        // 如何设置按钮对应的元素的属性
        // btn.value = '显示';
        this.value = '显示';

        isShow = false;
      } else {
        box.className = 'show';
        this.value = '隐藏';
        isShow = true;
      }
      
    }
  </script>
</body>
</html>
```

**使用hidden属性实现**

```html
<input type="button" id="btn" value="隐藏">
<br>
<div id="box">

</div>
<script>
    //1 获取元素
    var btn = document.getElementById('btn');

    var isShow = true;
    btn.onclick = function () {
        //3 控制div的显示隐藏
        var box = document.getElementById('box');
        if (isShow) {
            box.setAttribute("hidden", true);

            isShow = false;
        } else {
            box.removeAttribute("hidden");
            isShow = true;
        }

    }
</script>
```

### 5.3.3、美女相册

**取消超链接默认跳转行为**

```html
<a id="link" href="http://www.baidu.com">百度</a>
<script>
    var link = document.getElementById('link');
    link.onclick = function () {
        alert('点击我了');

        // 取消a标签的默认行为（跳转到href）
        return false;
    }
</script>
```

```html

<!DOCTYPE html>
<html>
<head lang="en">
    <meta charset="UTF-8">
    <title></title>
    <style type="text/css">
        body {
            font-family: "Helvetica","Arial",serif;
            color: #333;
            background-color: #ccc;
            margin: 1em 10%;
        }

        #imagegallery a {
            margin: 0px 20px 20px 0px;
            padding: 0px;
            display: inline;
        }

        #imagegallery a img {
            border: 0;
        }
    </style>
</head>
<body>
<h2>
    美女画廊
</h2>

<div id="imagegallery">
    <a href="images/1.jpg" title="美女A">
        <img src="images/1-small.jpg" width="100px" alt="美女1" />
    </a>
    <a href="images/2.jpg" title="美女B">
        <img src="images/2-small.jpg" width="100px" alt="美女2" />
    </a>
    <a href="images/3.jpg" title="美女C">
        <img src="images/3-small.jpg" width="100px" alt="美女3" />
    </a>
    <a href="images/4.jpg" title="美女D">
        <img src="images/4-small.jpg" width="100px" alt="美女4" />
    </a>
</div>

<div style="clear:both"></div>

<img id="image" src="images/placeholder.png" alt="" width="450px" />

<p id="des">选择一个图片</p>
    <script>
        //1 获取到所有的a标签
        var imagegallery = document.getElementById('imagegallery');
        var links = imagegallery.getElementsByTagName('a');
        //2 给所有的a标签注册事件
        for (var i = 0; i < links.length; i++) {
            // 所有的a标签对应的元素
            var link = links[i];
            // 注册事件
            link.onclick = function () {
                //4 切换图片
                // 获取占位的大`的img标签
                var image = document.getElementById('image');
                // 把img标签的src属性 设置为当前点击的a标签的href
                image.src = this.href;
                
                //5 设置p标签的内容
                var des = document.getElementById('des');
                // 当前点击的a标签的title属性
                // this.title
                // 如何设置p标签中显示的内容
                // console.dir(des);
                des.innerText = this.title;

                //3 取消a的默认行为
                return false;
            }
        }

        // 当循环结束之后 link是谁？？
        // link 是最后一个a标签
        // console.log(link);
    </script>
</body>
</html>
```

### 5.3.4、表单属性操作案例

**点击按钮禁用文本框**

```html
<input type="button" value="禁用文本框" id="btn">
<br>
<input type="text" id="txt" value='123'>
<script>
    // 获取元素
    var btn = document.getElementById('btn');
    // 注册事件
    btn.onclick = function () {
        console.log(txt.disabled);
        txt.disabled = true;
    }
</script>
```

**给文本框赋值，获取文本框的值**

```html
<input type="button" value="设置文本框的值" id="btn1">
<br>
<input type="text" id="txt" value='123'>
<script>
    var btn1 = document.getElementById('btn1');
    btn1.onclick = function () {
        var txt = document.getElementById('txt');
        // 设置文本框中的内容
        txt.value = 'hello world';
    }
</script>
```

**检测用户名是否是3-6位，密码是否是6-8位，如果不满足要求高亮显示文本框**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    .bg {
      background-color: yellow;
    }
  </style>
</head>

<body>
  <input type="text" id="txtUserName"> <br>
  <input type="password" id="txtUserPassword"> <br>
  <input type="button" value=" 登 录 " id="btnLogin">
  <script>
    // 检测用户名是否是3-6位，密码是否是6-8位，如果不满足要求高亮显示文本框
    var btnLogin = document.getElementById('btnLogin');

    btnLogin.onclick = function () {
      // 检测用户名是否是3-6位，密码是否是6-8位
      var txtUserName = document.getElementById('txtUserName');
      var txtUserPassword = document.getElementById('txtUserPassword');

      //检测用户名是否是3-6位
      if (txtUserName.value.length < 3 || txtUserName.value.length > 6) {
        txtUserName.className = 'bg';
        return;
      } else {
        txtUserName.className = '';
      }

      // 密码是否是6-8位
      if (txtUserPassword.value.length < 6 || txtUserPassword.value.length > 8) {
        txtUserPassword.className = 'bg';
        return;
      } else {
        txtUserPassword.className = '';
      }

      // 
      console.log('执行登录');
    }
  </script>
</body>

</html>
```

**设置下拉框中的选中项**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
</head>

<body>
  <input type="button" value="设置" id='btnSet'>
  <select id="selCities">
    <option value="1">北京</option>
    <option value="2">上海</option>
    <option value="3">杭州</option>
    <option value="4">郑州</option>
    <option value="5">武汉</option>
  </select>
  <script>
    // 1 给按钮注册事件
    var btnSet = document.getElementById('btnSet');
    btnSet.onclick = function () {
      // 2 获取下拉框中的所有option
      var selCities = document.getElementById('selCities');
      var options = selCities.getElementsByTagName('option');
      // 3 随机生成索引
      // Math.random() -> [0, 1)
      // Math.random() * 5 -> [0, 5)
      var randomIndex = parseInt(Math.random() * options.length);
      // 4 根据索引获取option，并让option选中
      var option = options[randomIndex];
      option.selected = true;
    }
  </script>
</body>

</html>
```

**模拟placeholder属性**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        /* 默认提示的文字颜色 */
        .default {
            color: #666;
        }

        /* 正常输入的文字颜色 */
        .normal {
            color: black;
        }
    </style>
</head>

<body>
    <input type="text" id="ip1" value="请输入用户名" class="default">
    <hr>
    <input type="text" placeholder="请输入用户名">
    <script>
        var ip1 = document.getElementById("ip1");
        // focus 获取焦点事件
        ip1.onfocus = function () {
            // console.log("获取焦点事件");
            // 如果value值是请输入用户名,并且class值是default,才清空输入框
            if (this.value === "请输入用户名" && this.className === "default") {
                // 清空输入框
                this.value = "";
                // 并且文字改为正常颜色
                this.className = "normal";
            }
        }

        // blur 失去焦点事件
        ip1.onblur = function () {
            // console.log("失去焦点事件");
            if (this.value === "") {
                this.value = "请输入用户名";
                this.className = "default"
            }
        }
    </script>
</body>

</html>
```

**全选反选**

```html
<!DOCTYPE html>
<html>

<head lang="en">
  <meta charset="UTF-8">
  <title></title>
  <style>
    * {
      padding: 0;
      margin: 0;
    }

    .wrap {
      width: 300px;
      margin: 100px auto 0;
    }

    table {
      border-collapse: collapse;
      border-spacing: 0;
      border: 1px solid #c0c0c0;
      width: 300px;
    }

    th,
    td {
      border: 1px solid #d0d0d0;
      color: #404060;
      padding: 10px;
    }

    th {
      background-color: #09c;
      font: bold 16px "微软雅黑";
      color: #fff;
    }

    td {
      font: 14px "微软雅黑";
      text-align: center;
    }

    tbody tr {
      background-color: #f0f0f0;
    }

    tbody tr:hover {
      cursor: pointer;
      background-color: #fafafa;
    }
  </style>

</head>

<body>
  <div class="wrap">
    <table>
      <thead>
        <tr>
          <th>
            <input type="checkbox" id="j_cbAll" />
          </th>
          <th>商品</th>
          <th>价钱</th>
        </tr>
      </thead>
      <tbody id="j_tb">
        <tr>
          <td>
            <input type="checkbox" />
          </td>
          <td>iPhone8</td>
          <td>8000</td>
        </tr>
        <tr>
          <td>
            <input type="checkbox" />
          </td>
          <td>iPad Pro</td>
          <td>5000</td>
        </tr>
        <tr>
          <td>
            <input type="checkbox" />
          </td>
          <td>iPad Air</td>
          <td>2000</td>
        </tr>
        <tr>
          <td>
            <input type="checkbox" />
          </td>
          <td>Apple Watch</td>
          <td>2000</td>
        </tr>

      </tbody>
    </table>
    <input type="button" value="  反 选  " id="btn">
  </div>
  <script>
    var j_tb = document.getElementById('j_tb');
    var inputs = j_tb.getElementsByTagName('input');
    // 1 全选
    // 1.1 获取父checkbox，注册点击事件
    var j_cbAll = document.getElementById('j_cbAll');
    j_cbAll.onclick = function () {
      // 1.2 找到所有子的checkbox，让这些checkbox的状态跟父checkbox保持一致

      for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        if (input.type === 'checkbox') {
          // 让子的checkbox的选中状态，和父checkbox的选中状态一致
          input.checked = this.checked;
        }
      }
    }

    // 2 当点击子的checkbox，如果所有的子的checkbox都被选中了，让父的checkbox也选中
    // 如果有一个子的checkbox没有被选中，父的checkbox也不被选中

    // 此处的循环，是遍历所有子的checkbox，注册点击事件
    for (var i = 0; i < inputs.length; i++) {
      var input = inputs[i];
      // 判断是否是checkbox
      if (input.type !== 'checkbox') {
        // 结束当前循环，继续下一次循环
        continue;
      }
      // 给子的checkbox注册点击事件
      input.onclick = function () {
        checkAllCheckBox();
      }
    }


    // 判断父的checkbox的状态 封装成函数
    function checkAllCheckBox() {
      // 假设所有的子的checkbox都被选中了
      var isAllChecked = true;
      // 判断是否所有的子的checkbox都被选中了
      for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        if (input.type !== 'checkbox') {
          continue;
        }
        // 判断当前的所有checkbox是否都被选中
        if (!input.checked) {
          isAllChecked = false;
        }
      }
      // 设置父的checkbox的状态
      j_cbAll.checked = isAllChecked;
    }

    // 3 反选
    // 3.1 给反选按钮注册点击事件
    var btn = document.getElementById('btn');
    btn.onclick = function () {
      // 3.2 找到所有的子的checkbox，让其反选
      for (var i = 0; i < inputs.length; i++) {
        var input = inputs[i];
        // 判断是否是checkbox
        if (input.type !== 'checkbox') {
          continue;
        }
        // 让子的checkbox反选
        input.checked = !input.checked;
        // 设置父的checkbox的状态
        checkAllCheckBox();
      }
    }
  </script>
</body>
</html>
```

<a id="p4-6"></a>
# 六、JavaScript Document对象属性一览

​        document可以通过一下属性可以查询指定属性值或给指定属性赋值.

​        **语法:**
​        document.属性名        获取属性值

​        document.属性名 = 值;        给指定属性设置值

​        **常用:**
​        **document.title             //设置或读取文档标题等价于HTML的```<title>```标签**

​        document.bgColor           //设置或获取页面背景色

​        document.fgColor           //设置或获取前景色(文本颜色)

​        document.linkColor         //设置或获取未点击过的链接颜色

​        document.alinkColor        //设置或获取激活链接(焦点在此链接上)的颜色

​        document.vlinkColor        //设置或获取已点击过的链接颜色

​        **document.cookie            //设置和读出cookie**

```html
cookie 是存储于访问者的计算机中的变量。每当同一台计算机通过浏览器请求某个页面时，就会发送这个 cookie。你可以使用 JavaScript 来创建和取回 cookie 的值。

设置cookie：
	每个cookie都是一个键/值对，可以把下面这样一个字符串赋值给document.cookie：
		document.cookie="userId=1001";
	document.cookie看上去就像一个属性，可以赋不同的值。但它和一般的属性不一样，改变它的赋值并不意味着丢失原来的值，例如连续执行下面两条语句：
		document.cookie="userId=1001";
		document.cookie="userName=zhangsan";
	这时浏览器将维护两个cookie，分别是userId和userName，因此给document.cookie赋值更像执行类似这样的语句：
		document.addCookie("userId=1001");
		document.addCookie("userName=zhangsan");

修改cookie:
	事实上，浏览器就是按照这样的方式来设置cookie的，如果要改变一个cookie的值，只需重新赋值，例如：
		document.cookie="userId=1002";

获取cookie的值:
	下面介绍如何获取cookie的值。cookie的值可以由document.cookie直接获得：
		var strCookie=document.cookie; 
	这将获得以分号隔开的多个名/值对所组成的字符串，这些名/值对包括了该域名下的所有cookie。例如：
		document.cookie="userId=1001";
        document.cookie="userName=zhangsan";
        var strCookie=document.cookie;
        console.log(strCookie); //userId=1001; userName=zhangsan
	由此可见，只能够一次获取所有的cookie值，而不能指定cookie名称来获得指定的值，这正是处理cookie值最麻烦的一部分。
	用户必须自己分析这个字符串，来获取指定的cookie值，例如，要获取userId的值,可以这样实现:
		document.cookie = "userId=1001";
    	document.cookie = "userName=zhangsan";

    	document.cookie = "userId=1002";

    	var strCookie = document.cookie;
    	console.log(strCookie); //userId=1001; userName=zhangsan

        function toCookieObj(strCookie) {
          var cookieObj = {};
          var arrCookie = strCookie.split(";");
          for (var i = 0; i < arrCookie.length; i++) {
            var arr = arrCookie[i].split("=");
            cookieObj[arr[0].trim()] = arr[1];
          }
          return cookieObj;
        }

        var cookieObj = toCookieObj(strCookie);
        console.log(cookieObj.userName);
```

​        document.URL ​        //返回当前文档的 URL

​        **document.images             //获取页面上的```<img>```标签**

​        images集合(页面中的图象)：可以使用指定的元素访问其各个属性

​        注:HTMLCollection 是一个集合，表示 HTML 元素的集合，它提供了可以遍历列表的方法和属性。
​        HTML DOM 中的 HTMLCollection 是“活”的；如果基本的文档改变时，那些改变通过所有 HTMLCollection 对象会立即显示出来。
​        HTMLCollection 对象是只读的，不能给它添加新元素，即使采用 JavaScript 数组语法也是如此。
​        HTMLCollection 对象和 NodeList 对象很相似

```js
document.images.length      //对应页面上<img>标签的个数
document.images[0]          //第1个<img>标签
document.images.item(2)          //第3个<img>标签
```

​        forms集合(页面中的表单):可以使用指定的元素访问其各个属性

```js
document.forms                 //对应页面上的<form>标签
document.forms.length          //对应页面上<form>标签的个数
document.forms[0]              //第1个<form>标签
document.forms[i].length       //第i-1个<form>中的控件数
document.forms[i].elements[j]  //第i-1个<form>中第j-1个控件
```

​        注：除了forms/images,还有anchors/links/applets

​        anchors​        返回对文档中所有 Anchor 对象的引用。(锚点)

​        links​        返回对文档中所有 Area 和 Link 对象引用(超链接)。

​        applets​        返回对文档中所有 Applet 对象的引用。

​        注:Applet是采用Java编程语言编写的小应用程序，该程序可以包含在 HTML（标准通用标记语言的一个应用）页中，与在页中包含图像的方式大致相同。

​	含有Applet的网页的HTML文件代码中部带有```<applet>``` 和```</applet>```这样一对标记，当支持Java的网络浏览器遇到这对标记时，就将下载相应的小应用程序代码并在本地计算机上执行该Applet。

​        **body        获取到body元素节点**

​        **head        获取到head元素节点**

<a id="p4-7"></a>
# 七、JavaScript获取层次节点

## 7.1、节点概念

​	节点最常见的类型有元素节点、属性节点、注释节点和文本节点.

​        节点的层次结构可以划分为：父节点与子节点、兄弟节点、祖先后代节点这三种。**当我们获取其中一个元素节点的时候，就可以使用层次节点属性来获取它相关层次的节点**。

**示例:**

```html
<div id="div1">
    <p>我是div中的p段落</p>
    <!--我是页面中的注释-->
    <div>我是div1中的子div</div>
    我是div的纯文本内容
    <h2>我是div中的h2标题标签</h2>
</div>
```

​        上面的案例中: id为div1的元素是父节点,并且本身也是元素节点; div1里面的节点都是它的子节点;那么到底有多少个子节点呢?

​        我们知道标签元素都是元素节点,纯文本内容就是文本节点,属性就是属性节点,注释就是注释节点,那么子节点看似是有5个，但是不是.....我们进行深入研究。

​        childNodes​        获取当前元素节点的所有子节点

​        因为浏览器会把节点之间的空白符当作文本结点处理。

```html
<div>
    javascript  
    <p>javascript</p> <!-- ←空白节点 -->
    <div>jQuery</div> <!-- ←空白节点 -->
    <h5>PHP</h5> <!-- ←空白节点 -->
</div>
```

​        4个可见结点 + 3个看不出来的空白节点 = 7个节点
​        注:文字节点之前之后的空格都算是内容的一部分。

​        这些节点又有三个非常有用的属性，分别为：nodeName、nodeType 和nodeValue。

​        **信息节点属性:**

​        节点类型​        nodeName​        nodeType​        nodeValue

​        元素​        ​        元素名称​        ​        1​        ​        ​        null

​        属性​        ​        属性名称​        ​        2​        ​        ​        属性值

​        文本​        ​        #text​        ​        ​      3​        ​        ​        文本内容

​        注释​        ​        #comment​        ​    8 ​        ​        ​       注释内容

## 7.2、获取层次节点

![](images04_dom/微信截图_20200709175921.png)

​        firstChild​        获取当前元素节点的第一个子节点

​        **firstElementChild​        获取当前元素节点的第一个元素子节点**   

​		IE9以下版本和Safari不支持；​	

```js
function getFirstElementChild(element) {
    var node, nodes = element.childNodes, i = 0;
    while (node = nodes[i++]) {
        if (node.nodeType === 1) {
            return node;
        }
    }
    return null;
}
```

​        lastChild​        获取当前元素节点的最后一个子节点

​        **lastElementChild​        获取当前元素节点的最后一个元素子节点**

​        ownerDocument​        获取该节点的文档节点

​        **parentNode​        获取当前节点的父节点**

​        nextSibling​        获取当前节点的后一个同级节点

​        **nextElementSibling​        获取当前节点的后一个同级元素节点**

```js
// 处理浏览器兼容性
// 获取下一个兄弟元素
 function getNextElementSibling(element) {
    var el = element;
    while (el = el.nextSibling) {
      if (el.nodeType === 1) {
          return el;
      }
    }
    return null;
  }
```

​        previousSibling​        获取当前节点的前一个同级节点

​        **previousElementSibling​        获取当前节点的前一个同级元素节点**

​        attributes​        获取当前元素节点的所有属性节点集合

​        **childElementCount​        获取当前节点的元素节点的个数**

​        **children​        获取当前节点的所有元素子节点**

​        childNodes        获取当前节点的所有子节点

**注意：**

​	childNodes和children的区别，childNodes获取的是子节点，children获取的是子元素

​	nextSibling和previousSibling获取的是节点，获取元素对应的属性是nextElementSibling和previousElementSibling获取的是元素

​	nextElementSibling和previousElementSibling有兼容性问题，IE9以后才支持

<a id="p4-8"></a>
# 八、JavaScript操作节点

## 8.1、操作节点API

1、createElement()​        创建一个元素节点

```js
document.createElement(‘标签名’)
document.createElement('p'); //创建一个元素节点,这里写字符串标签名
```

2、appendChild()​        将新节点追加到子节点列表的末尾

```js
元素节点.appendChild(‘节点’)
var box = document.getElementById('box'); //获取某一个元素节点
var p = document.createElement('p'); //创建一个新元素节点<p>
box.appendChild(p); //把新元素节点<p>添加子节点末尾
```

3、createTextNode()​        创建一个文本节点

```js
document.createTextNode(‘文本值’)
var text = document.createTextNode('段落'); //创建一个文本节点
p.appendChild(text); //将文本节点添加到子节点末尾
```

4、insertBefore(新节点,已有节点)        可在已有的子节点前插入一个新的子节点.
​	父节点.insertBefor(新节点,已有节点)
​	old节点的父节点.insertBefore(new,old);
​	需要注意的是insertBefore()方法可以给当前元素的前面创建一个节点，但却没有提供给当前元素的后面创建一个节点。

```js
function insertAfter(newElement, targetElement) {
    //得到父节点
    var parent = targetElement.parentNode;
    //如果最后一个子节点是当前元素，那么直接添加即可
    if (parent.lastChild === targetElement) {
        parent.appendChild(newElement);
    } else {
        //否则，在当前节点的下一个节点之前添加
        parent.insertBefore(newElement, targetElement.nextElementSibling);
    }
}
```

5、repalceChild()        可将某个子节点替换为另一个。
​	父节点.insertBefor(新节点,旧节点)

```js
parentDiv.replaceChild(p,box); //把<div>换成了<p>
```

6、cloneNode()        复制节点
​	元素节点.cloneNode(Boolean)
​	可选。该方法将复制并返回调用它的节点的副本。如果传递给它的参数是 true，它还将递归复制当前节点的所有子孙节点。否则，它只复制当前节点。

7、removeChild()        删除父节点下指定的子节点
​	父节点.removeChild(子节点)

注:无论是插入到节点之前还是替换节点,节点本身自己不能操作,需要通过父节点来完成。

**向页面插入带标签内容，效率测试：**

```html
<!--通过innerHTML插入内容-->
<script>
    function fn() {
        var d1 = new Date(); 

        for (var i = 0; i < 1000; i++) {
            document.body.innerHTML += '<div style="width:100px; height:2px; border:1px solid blue;"></div>';
        }
        var d2 = new Date();
        console.log(d2 - d1);
    }
    fn();
</script>

<!--通过innerHTML插入内容-->
<script>
    function fn() {
        var d1 = new Date();
        var array = [];
        for ( var i = 0; i < 1000; i++ ) {
            array.push('<div style="width:100px; height:2px; border:1px solid blue;"></div>');
        }
        document.body.innerHTML = array.join('');
        var d2 = new Date();
        console.log( d2 - d1 );
    }
    fn();
</script>

<!--通过createElement插入内容-->
<script>
    function fn() {
        var d1 = new Date();
        
        for ( var i = 0; i < 1000; i++ ) {
            var div = document.createElement('div');
            div.style.width = '100px';
            div.style.height = '2px';
            div.style.border = '1px solid red';
            document.body.appendChild( div );
        }
        var d2 = new Date();
        console.log( d2 - d1 );
    }
    fn();
</script>
```

## 8.2、案例

**根据数据动态创建表格**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    #box table {
      border-collapse: collapse;
    }
  </style>
</head>

<body>
  <div id="box"></div>
  <script>
    // var s = {name: 'zs', subject: '语文', score: 90};
    // 模拟数据
    var datas = [{
        name: 'zs',
        subject: '语文',
        score: 90
      },
      {
        name: 'ls',
        subject: '数学',
        score: 80
      },
      {
        name: 'ww',
        subject: '英语',
        score: 99
      },
      {
        name: 'zl',
        subject: '英语',
        score: 100
      },
      {
        name: 'xs',
        subject: '英语',
        score: 60
      },
      {
        name: 'dc',
        subject: '英语',
        score: 70
      }
    ];

    // 表头数据
    var headDatas = ['姓名', '科目', '成绩', '操作'];

    // 1 创建table 元素
    var table = document.createElement('table');
    box.appendChild(table);

    // 2 创建表头
    var thead = document.createElement('thead');
    table.appendChild(thead);

    var tr = document.createElement('tr');
    thead.appendChild(tr);
    tr.style.height = '40px';
    tr.style.backgroundColor = 'lightgray';

    // 遍历头部数据，创建th
    for (var i = 0; i < headDatas.length; i++) {
      var th = document.createElement('th');
      tr.appendChild(th);
      // th.innerText
      setInnerText(th, headDatas[i]);
    }

    // 3 创建数据行
    var tbody = document.createElement('tbody');
    table.appendChild(tbody);
    tbody.style.textAlign = 'center';
    for (var i = 0; i < datas.length; i++) {
      // 一个学生的成绩 {name: 'zl', subject: '英语', score: 100},
      var data = datas[i];
      tr = document.createElement('tr');
      tbody.appendChild(tr);

      // 遍历对象
      for (var key in data) {
        var td = document.createElement('td');
        tr.appendChild(td);
        setInnerText(td, data[key]);
      }
      // 生成删除对应的列
      td = document.createElement('td');
      tr.appendChild(td);
      // 删除的超链接
      var link = document.createElement('a');
      td.appendChild(link);
      link.href = 'javascript:void(0)';
      setInnerText(link, '删除');

      link.onclick = linkDelete;
    }

    function linkDelete() {
      // removeChild()
      // 获取父元素
      // 
      // 获取要删除的行
      var tr = this.parentNode.parentNode;
      tbody.removeChild(tr);
      return false;
    }

    function setInnerText(element, content) {
      // 判断当前浏览器是否支持 innerText
      if (typeof element.innerText === 'string') {
        element.innerText = content;
      } else {
        element.textContent = content;
      }
    }
  </script>
</body>

</html>
```

**选择水果**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>Title</title>
    <style>
        select {
            width: 200px;
            height: 200px;
            background-color: #33cccc;
            font-size: 20px;
        }
    </style>
</head>

<body>
    <select id="left" multiple="multiple">
        <option value="0">苹果</option>
        <option value="1">橘子</option>
        <option value="2">梨</option>
        <option value="3">西瓜</option>
        <option value="4">水蜜桃</option>
    </select>

    <input type="button" value=">>" id="btn1">
    <input type="button" value="<<" id="btn2">
    <input type="button" value=">" id="btn3">
    <input type="button" value="<" id="btn4">

    <select id="right" multiple="multiple">

    </select>

    <script>
        var left = document.getElementById("left");
        var right = document.getElementById("right");

        // 保留一份原始副本
        var conetent = left.innerHTML;

        // 当我们点击btn1的时候,把左边的都移到右边
        var btn1 = document.getElementById("btn1");
        var btn2 = document.getElementById("btn2");
        var btn3 = document.getElementById("btn3");
        var btn4 = document.getElementById("btn4");

        btn1.onclick = function () {
            // childElementCount 获取元素子节点的个数
            if (left.childElementCount != 0) {
                right.innerHTML = conetent;

                left.innerHTML = "";
            }
        }

        // 当我们点击btn2的时候,把右边的都移到左边
        btn2.onclick = function () {
            if (right.childElementCount != 0) {
                left.innerHTML = conetent;
                right.innerHTML = "";
                // 把 leftToRight数组清空;
                leftToRight = [];
            }
        }

        // 当我们点击btn3的时候,哪个option处于选中状态,则移到右边
        var leftToRight = [];

        btn3.onclick = function () {
            // 点击按钮3,遍历左边所有的option,如果option的selected属性为true,则移到右边
            // 获取左侧所有的option
            var leftOptions = left.children;

            for (var i = 0; i < leftOptions.length; i++) {
                // 获取得到每个左侧的option
                var op = leftOptions[i];
                if (op.selected) {
                    // 不能在这里面使用下标
                    leftToRight.push(op);

                    // 不要在这里面直接挪动,而是放到循环外面挪动
                    // 状态改为不选中
                    op.selected = false;
                }
            }

            // 为了移到右侧,还能保持顺序
            var leftToRightSort = sortArray(leftToRight); //西瓜  水蜜桃 苹果    

            // 把数组里面的元素节点放到右边
            for (var i in leftToRightSort) {
                if (leftToRightSort[i]) {
                    right.appendChild(leftToRightSort[i]);
                }
            }
        }

        function sortArray(arr) { // 西瓜  水蜜桃 苹果 
            var newArr = [];
            for (var i = 0; i < arr.length; i++) {
                var op = arr[i]; //获取到参数数组的每一个option
                newArr[op.value] = op; //[苹果,undefined,undefined,西瓜,水蜜桃]
            }
            return newArr;
        }
    </script>
</body>

</html>
```


---

<a id="p5"></a>

# 第5篇 · JavaScript DOM编程（特效篇）

---

<a id="p5-1"></a>
# 一、JavaScript操作表格

## 1.1、操作表格API

**1、HTML DOM中，给table操作提供了一些属性和方法。**

**table元素节点的独有属性和方法:**

| 属性或方法      | 说明                                         |
| --------------- | -------------------------------------------- |
| caption         | 保存着```<caption>```元素的引用              |
| tBodies         | 保存着```<tbody>```元素的HTMLCollection 集合 |
| tFoot           | 保存着对```<tfoot>```元素的引用              |
| tHead           | 保存着对```<thead>```元素的引用              |
| createTHead()   | 创建```<thead>```元素，并返回引用            |
| createTFoot()   | 创建```<tfoot>```元素，并返回引用            |
| createTBody()   | 创建```<tbody>```元素,并且返回引用           |
| createCaption() | 创建```<caption>```元素，并返回引用          |
| deleteTHead()   | 删除```<thead>```元素                        |
| deleteTFoot()   | 删除```<tfoot>```元素                        |
| deleteCaption() | 删除<```caption>```元素                      |

**2、```<tbody>```/```<thead>```/```<tfoot>```/```<table>```元素添加的属性和方法**

| 属性或方法     | 说明                                        |
| -------------- | ------------------------------------------- |
| rows           | 保存着指定元素中行的HTMLCollection          |
| deleteRow(pos) | 删除指定位置的行                            |
| insertRow(pos) | 向rows 集合中的指定位置插入一行，并返回引用 |

**3、```<tr>```元素添加的属性和方法**

| 属性或方法      | 说明                                            |
| --------------- | ----------------------------------------------- |
| cells           | 保存着```<tr>```元素中单元格的HTMLCollection    |
| deleteCell(pos) | 删除指定位置的单元格                            |
| insertCell(pos) | 向cells集合的指定位置插入一个单元格，并返回引用 |

## 1.2、案例

**使用新API实现动态创建表格；**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        /* 我们如果直接写标签名,这就是所谓的标签选择器 */
        /* 选择器{}     给指定的标签添加样式 */
        /* 选择器1,选择器2,...{}    给多个指定的元素添加样式 */
        table,
        td,
        th {
            border: 1px solid black;
        }

        /* 
            一般情况下: 我们给表格设置宽度;
            一般情况下: 我们给行设置高度;
         */
        table {
            /* border-collapse 边框合并 */
            border-collapse: collapse;
            margin: 0 auto;
            width: 800px;
            /* 我们给表格设置文本居中,那么td单元格会继承到该样式 */
            /* text-align: center;  */
        }

        tr {
            height: 38px;
        }

        caption {
            font-size: 40px;
            font-weight: bold;
            height: 80px;
            line-height: 80px;
        }

        /* tbody>tr    选择tbody里面所有的行 */
        tbody>tr:nth-child(odd) {
            background: #eee;
        }

        thead td {
            text-align: center;
            font-weight: bold;
        }
    </style>
</head>

<body>
    <table id="tab1">

    </table>
    <script>
        // 获取得到table元素节点
        var stuTable = document.getElementById("tab1");

        // 创建thead、tbody
        var thead = stuTable.createTHead();
        var tbody = stuTable.createTBody();


        // 表头数据
        var headDatas = ['姓名', '科目', '成绩', '操作'];

        // 在thead里面创建一行
        var theadTr = thead.insertRow(0);

        for (var i in headDatas) { //使用for in来遍历数组的时候,in前面的变量表示数组的下标
            // 获取每一条表头数据
            // theadTr.insertCell(i) 根据下标创建行,并且给行插入内容
            theadTr.insertCell(i).innerText = headDatas[i];;
        }

        // 模拟数据
        var datas = [{
                name: '张三',
                subject: '语文',
                score: 90
            },
            {
                name: '李四',
                subject: '数学',
                score: 80
            },
            {
                name: '王武',
                subject: '英语',
                score: 99
            },
            {
                name: '马六',
                subject: '英语',
                score: 100
            },
            {
                name: '田七',
                subject: '英语',
                score: 60
            },
            {
                name: '赵八',
                subject: '英语',
                score: 70
            }
        ];

        // 根据上述数据,在tbody里面生成行及其单元格和数据
        // datas数组里有几个元素,就应该创建几行; 每个元素里面的对象有多少个key-vaue就创建多少个单元格
        for (var i in datas) { // datas里面存储的6个学生对象
            // 通过下标获取到每个学生对象
            var stuInfo = datas[i];

            // 每个学生都对应了一行数据
            var tbodyTr = tbody.insertRow(i);

            var index = 0;
            // 学生的每一个数据就是一个单元格
            for (var j in stuInfo) { // j在遍历对象的时候,是字符串的key
                // j  "name"    "subject"   "score"
                tbodyTr.insertCell(index++).innerText = stuInfo[j];
            }

            tbodyTr.insertCell(index).innerHTML = "<a href='javascript:void(0)'>删除</a>";

        }
    </script>

</body>

</html>
```

## 1.3、练习

**使用JavaScript创建如下表格:**

![1573046337814](images04_dom/1573046337814.png)

**实现如图功能:**

​    1、动态计算数量和商品总价格

​    2、可以实现删除和修改操作

​    3、可以实现添加商品操作

![1573046370946](images04_dom/1573046370946.png)

<a id="p5-2"></a>
# 二、JavaScript事件（重点）

## 2.1、事件介绍

​	JavaScript与HTML之间的交互是通过事件来实现的，**事件就是用户或浏览器自身执行的某种动作**，比如click、mounseover、load……,而**响应事件的函数就叫做事件处理函数**。

​        事件(Event)是JavaScript应用跳动的心脏 ，也是把所有东西粘在一起的胶水。当我们与浏览器中Web页面进行某些类型的交互时，事件就发生了。事件可能是用户在某些内容上的点击、鼠标经过某个特定元素或按下键盘上的某些按键。事件还可能是Web浏览器中发生的事情，比如说某个Web页面加载完成，或者是用户滚动窗口或改变窗口大小。

**事件：触发-响应机制**

**事件三要素：**

- 事件源:触发(被)事件的元素
- 事件名称: click 点击事件
- 事件处理程序:事件触发后要执行的代码(函数形式)

![1573104570603](images04_dom/1573104570603.png)

**事件发生常见情况:**

> 当鼠标点击某个地方的时候,发生了...
>
> 当鼠标移入某个地方的时候,发生了...
>
> 页面载入完毕的时候,发生了...
>
> 当输入框获取光标的时候,发生了...
>
> 当输入框失去光标的时候,发生了...
>
> 当按下某个键的时候,发生了...

​        通过使用 JavaScript ，你可以监听特定事件的发生，并规定让某些事件发生以对这些事件做出响应。JavaScript 事件是由访问Web页面的用户引起的一系列操作，例如：用户点击。当用户执行某些操作的时候，再去执行一系列代码。

​        注意：事件通常与函数配合使用，当事件发生时函数才会执行。

## 2.2、事件三种使用方式

事件一般是用于浏览器和用户操作进行交互。

使用JavaScript有三种方法：内联(行内)、脚本和事件侦听;

### 2.2.1、内联方式

​	这种模型是最传统简单的一种处理事件的方法。在内联模型中，事件处理函数是HTML标签的一个属性，用于处理指定事件。

​	虽然内联在早期使用较多，但它是和HTML混写的，并没有与HTML分离。

```html
//在HTML 中把事件处理函数作为属性执行JS代码
<div id="div1" onclick="this.style.background='blue'">我是div里面的文字</div>

//在HTML 中把事件处理函数作为属性执行JS 函数1
<div id="div1" onclick="myfun1(this)">我是div里面的文字</div>

<script>
    function myfun1(t){t.style.background='blue'}
</script>
```

​        注:内联可以给一个元素定义的同一事件添加多个执行函数

```html
<div id="div1" onclick="myfun1(),myfun2()">我是div里面的文字</div>
```

### 2.2.2、脚本方式

​	由于内联模型违反了HTML 与JavaScript 代码层次分离的原则。为了解决这个问题，我们可以在JavaScript 中处理事件。这种处理方式就是脚本模型。

**获取元素,给其加事件,事件赋值某个函数名,切记不加括号.**

```js
// 获取页面元素
var div1 = document.getElementById("div1");

// 定义事件函数
function myfun1(){
  div1.style.background="blue";
}

// 给元素绑定事件及其事件函数
div1.onclick=myfun1;
```

**匿名函数写法:**

```js
var div1 = document.getElementById("div1");

div1.onclick=function(){
	div1.style.background="blue";
}

 // 脚本方式移除事件处理函数
div1.onclick = null;
```

​        通过匿名函数，可以直接触发对应的代码。

​        注:脚本形式不可以给同一事件添加多个执行函数;

### 2.2.3、事件监听(侦听)方式

​        JavaScript中定义了两个方法，用于添加事件和删除事件处理程序的操作：addEventListener()和removeEventListener()。

​        所有DOM 节点中都包含这两个方法，并且它们都接受3个参数；事件类型、事件处理函数、冒泡或捕获的布尔值(true 表示捕获，false 表示冒泡)。

​        标准的浏览器使用W3C定义的addEventListener函数绑定，函数定义如下：

​        function addEventListener(string eventType, function eventFunc, [bool useCapture=false])
​        ​        参数eventType: 事件名称，如click、mouseover…
​        ​        eventFunc: 绑定到事件中执行的动作
​        ​        useCapture: 指定是否绑定在捕获阶段，true为是，false为否，默认为false。
​        注:事件冒泡和捕捉在之后讲!

```js
document.addEventListener('click', function () {
  alert('document');
});

box.addEventListener('click', function () {
  alert('Lee');
});
```

​        **事件侦听的优势:**

​        1、当同一个对象使用.onclick的写法触发多个方法的时候，后一个方法会把前一个方法覆盖掉，也就是说，在对象的onclick事件发生时，只会执行最后绑定的方法。

​        而用事件监听则不会有覆盖的现象，每个绑定的事件都会被执行。如下：

```js
window.onload = function(){

  var btn = document.getElementById("yuanEvent");
  btn.onclick = function(){
    alert("第一个事件");
  }

  btn.onclick = function(){
    alert("第二个事件");
  }

  btn.onclick = function(){
    alert("第三个事件");
  }
}

最后只输出：第三个事件，因为后一个方法都把前一个方法覆盖掉。

原生态的事件绑定函数addEventListener：
function eventOne (){
  alert("第一个监听事件");
}

function eventTwo(){
  alert("第二个监听事件");
}

window.onload = function(){
  var btn = document.getElementById("yuanEvent");
  //addEventListener：绑定函数
  btn.addEventListener("click",eventOne);
  btn.addEventListener("click",eventTwo);
}
输出：第一个监听事件和第二个监听事件
```

​        2、采用事件监听给对象绑定方法后，可以解除相应的绑定，写法如下：

```js
var eventOne = function(){
  alert("第一个监听事件");
}
function eventTwo(){
  alert("第二个监听事件");
}
  var btn = document.getElementById("yuanEvent");
  btn.addEventListener("click",eventOne);
  btn.addEventListener("click",eventTwo);
  btn.removeEventListener("click",eventOne);
输出：第二个监听事件
解除绑定事件的时候一定要用函数的句柄，把整个函数写上是无法解除绑定的。
```

### 2.2.4、IE兼容

IE9以前不支持addEventListener和removeEventListener方法；

实现了两个类似的方法：

- attachEvent
- detachEvent

```js
// 第一个参数，事件的名称前要加 on
box.attachEvent('onclick', eventCode);
box.detachEvent('onclick', eventCode);

function eventCode() {
  console.log('点击后执行');
}
```

这两个方法都接受两个相同的参数。

​	1.事件处理程序名称

​	2.事件处理程序方法

attachEvent——兼容：IE7、IE8；不兼容firefox、chrome、IE9、IE10、IE11、safari、opera

addEventListener——兼容：firefox、chrome、IE、safari、opera；不兼容IE7、IE8

```js
function addEventListener(element, type, fn) {
    if (element.addEventListener) {
        element.addEventListener(type, fn, false);
    } else if (element.attachEvent) {
        element.attachEvent('on' + type, fn);
    } else {
        element['on' + type] = fn;
    }
}

function removeEventListener(element, type, fn) {
    if (element.removeEventListener) {
        element.removeEventListener(type, fn, false);
    } else if (element.detachEvent) {
        element.detachEvent('on' + type, fn);
    } else {
        element['on' + type] = null;
    }
}

addEventListener(box, "click", function () {
    console.log("兼容解决策略")
})
```

## 2.3、常用的事件类型

​        JavaScript 可以处理的事件类型为：鼠标事件、键盘事件、框架事件、表单事件。

​        所有的事件处理函数都会都有两个部分组成，on + 事件名称，例如click 事件的事件处理函数就是：onclick。在这里，我们主要谈论脚本的方式来构建事件，违反分离原则的内联，我们忽略掉。

**鼠标事件:**

1、click		当用户点击某个对象时调用的事件句柄。

2、dblclick	当用户双击某个对象时调用的事件句柄。

3、mousedown	鼠标按钮被按下。

4、mouseup		当用户释放鼠标按钮时触发[鼠标左右键]。

5、mouseover	鼠标移到某元素之上。

6、mouseout	鼠标从某元素移开。

7、mousemove	当鼠标被移动。

8、mouseenter	当鼠标指针移动到元素上时触发。

9、mouseleave	当鼠标指针移出元素时触发

 onmouseenter 事件类似于 onmouseover 事件。 唯一的区别是 onmouseenter 事件不支持冒泡 。

**键盘事件:**

1、keydown：当用户按下键盘上任意键触发，如果按住不放，会重复触发。

​        onkeydown = function () {alert('Lee');};

2、keypress：当用户按下键盘上的字符键触发，如果按住不放，会重复触发。

​        onkeypress = function () {alert('Lee');};

3、keyup：当用户释放键盘上的键触发。

​        onkeyup = function () {alert('Lee');};

​        注:键盘事件一般用在可获取焦点的元素上或doument对象上

​​​        在发生键盘事件时，键盘事件对象的keyCode 属性中会包含一个代码，与键盘上一个特定的键对应。

**keypress 和 keydown 是有区别?**

​        1.keydown 先于 keypress 发生。

​        2.keypress 无法系统按钮。

​        3.keydown 捕获的 keyCode 不区分字母大小，而 keypress 区分。

​        4.keypress是在用户按下并放开任何字母数字键时发生。系统按钮（例如，箭头键和功能键）无法得到识别。

​        5.keyup 是在用户放开任何先前按下的键盘键时发生。

​        6.keydown 是在用户按下任何键盘键（包括系统按钮，如箭头键和功能键）时发生。

**框架/对象（Frame/Object）事件**

1、load		当页面完全加载后在window 上面触发，或当框架集加载完毕后在框架集上触发。当页面完全加载所有内容（包括图像、脚本文件、CSS 文件等）执行

2、unload		用户退出页面。 ( `<body>` 和 `<frameset>`)

```html
<div id="box">
    
</div>
<script>
    // BOM   onload  页面加载完成之后执行  
    // 页面加载完成 页面上所有的元素创建完毕，并且引用的外部资源下载完毕（js，css，图片）
    // window.onload = function () {
    onload = function () {
    var box = document.getElementById('box');
    console.log(box);
    }

    // window.onunload = function () {
    // 页面卸载的时候执行
    onunload = function () {
    // 在onunload中所有的对话框都无法使用 window 对象被冻结
    // Blocked alert('欢迎下次再来') during unload.
    // alert('欢迎下次再来');
    console.log('bye bye');
    }
    
    // f5 刷新页面  
    // 1 卸载页面
    // 2 重新加载页面
</script>
```

3、beforeunload		该事件在即将离开页面（刷新或关闭）时触发

4、hashchange		该事件在当前 URL 的锚部分发生修改时触发。

5、resize			当窗口或框架的大小变化时在window 或框架上触发。

6、scroll				当用户滚动时触发。

**表单事件:**

1、select	当用户选择文本框(input 或textarea)中的一个或多个字符触发。

2、change	该事件在表单元素的内容改变时触发( `<input>`, `<keygen>`, `<select>`, 和 `<textarea>`)。

3、focus	元素获取焦点时触发。

4、blur		元素失去焦点时触发。

5、submit	当用户点击提交按钮在```<form>```元素上触发。

6、reset		当用户点击重置按钮在```<form>```元素上触发。

```html
<form action="" onsubmit="myFun1()" onreset="myfun2()">
    <input type="text" name="userName" placeholder="请输入您的名字" > <br>
    <input type="submit" value="提交表单"><input type="reset" value="重置表单">
</form>
<script>
    function myFun1(){
        var userName = document.getElementsByTagName("input")[0].value;
        alert("hello,"+userName);
    }
    function myfun2(){alert("您重置了表单");}
</script>
```

7、input		元素获取用户输入时触发

## 2.4、事件的冒泡和捕获

### 2.4.1、事件冒泡和捕获

​	什么是事件冒泡?

​        在一个对象上触发某类事件（比如单击click事件），如果此对象定义了此事件的处理程序，那么此事件就会调用这个处理程序，如果没有定义此事件处理程序或者事件返回true，那么这个事件会向这个对象的父级对象传播，从里到外，直至它被处理（父级对象所有同类事件都将被激活），或者它到达了对象层次的最顶层，即document对象（有些浏览器是window）。

​        事件的冒泡：事件按照从最特定的事件目标到最不特定的事件目标的顺序触发。

​        事件冒泡可以形象地比喻为把一颗石头投入水中，泡泡会一直从水底冒出水面。也就是说，事件会从最内层的元素开始发生，一直向上传播，直到document对象。

```html
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Document</title>
        <style>
            #box1 {
                width: 300px;
                height: 300px;
                background-color: red;
            }

            #box2 {
                width: 200px;
                height: 200px;
                background-color: green;
            }

            #box3 {
                width: 100px;
                height: 100px;
                background-color: blue;
            }
        </style>
    </head>
    <body>
        <div id="box1">
            <div id="box2">
                <div id="box3">
                </div>
            </div>
        </div>
        <script>
            // addEventListener 的第三个参数的作用
            var box1 = document.getElementById('box1');
            var box2 = document.getElementById('box2');
            var box3 = document.getElementById('box3');

            var array = [box1, box2, box3];

            // addEventListener 的第三个参数为false的时候 ： 事件冒泡
            // addEventListener 的第三个参数为true的时候 ：  事件捕获

            for (var i = 0; i < array.length; i++) {
                array[i].addEventListener('click', function () {
                    console.log(this.id);
                }, false);
            }

            document.body.addEventListener('click', function () {
                console.log('body');
            }, false);
        </script> 
    </body>
</html>
```

​	事件的捕获：与事件冒泡相反，事件会从最外层开始发生，直到最具体的元素。

​        事件捕获时，父级元素先触发，子级元素后触发。

​        可以自己选择绑定事件时采用事件捕获还是事件冒泡，方法就是绑定事件时通过addEventListener函数，它有三个参数，第三个参数若是true，则表示采用事件捕获，若是false，则表示采用事件冒泡。

​        IE9以前的版本只支持事件冒泡，不支持事件捕获，它也不支持addEventListener函数，不会用第三个参数来表示是冒泡还是捕获，它提供了另一个函数attachEvent。

### 2.4.2、事件的三个阶段

事件的处理过程主要有三个阶段：捕获阶段，目标阶段，冒泡阶段；

**捕获阶段：**当我们在 DOM 树的某个节点发生了一些操作（例如单击、鼠标移动上去），就会有一个事件发射过去。这个事件从 Window 发出，不断经过下级节点直到触发的目标节点。在到达目标节点之前的过程，就是捕获阶段（Capture Phase）。事件由页面元素接收，逐级向下，到具体的元素。

![](images04_dom/%E5%BE%AE%E4%BF%A1%E6%88%AA%E5%9B%BE_20200713220319.png)

**目标阶段：**当事件不断的传递直到目标节点的时候，最终在目标节点上触发这个事件，就是目标阶段。具体的元素本身。

**冒泡阶段：**事件冒泡即事件开始时，由最具体的元素接收（也就是事件发生所在的节点），然后逐级传播到较为不具体的节点。跟捕获相反，具体元素本身，逐级向上，到页面元素（我们平时用的事件绑定就是利用的事件冒泡的原理）。

![](images04_dom/%E5%BE%AE%E4%BF%A1%E6%88%AA%E5%9B%BE_20200713220535.png)

**W3C ： 任何事件发生时，先从顶层开始进行事件捕获，直到事件触发到达事件源，再从事件源向上进行事件捕获（事件冒泡）。**

事件对象.eventPhase属性可以查看事件触发时所处的阶段

![1573104917347](images04_dom/1573104917347.png)

### 2.4.3、事件对象的属性和方法（核心）

```html
	在标准的DOM 事件中，event 对象包含创建它的特定事件有关的属性和方法。Event 对象代表事件的状态，比如事件在其中发生的元素、键盘按键的状态、鼠标的位置、鼠标按钮的状态。

什么时候会产生Event 对象呢? 
	事件对象，我们一般称作为event 对象，这个对象是浏览器通过函数把这个对象作为参数传递过来的。通过事件绑定的执行函数是可以得到一个隐藏参数的,这个参数其实就是event对象。

事件通常与函数结合使用，函数不会在事件发生前被执行！
```

```js
var oDIv = document.getElementById('box');

oDiv.onclick = function(event){
    .........
}
```

- event.eventPhase	**返回事件传播的当前阶段。**
- event.target || event.srcElement     **返回触发此事件的元素（事件的目标节点）。**
- event.currentTarget      **返回其事件监听器触发该事件的元素**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    #box1 {
      width: 300px;
      height: 300px;
      background-color: red;
    }

    #box2 {
      width: 200px;
      height: 200px;
      background-color: green;
    }

    #box3 {
      width: 100px;
      height: 100px;
      background-color: blue;
    }
  </style>
</head>

<body>
  <input type="button" value="按钮" id="btn">
  <div id="box1">
    <div id="box2">
      <div id="box3">
      </div>
    </div>
  </div>
  <script>
    // 通过事件对象，可以获取到事件发生的时候和事件相关的一些数据
    var btn = document.getElementById('btn');
    btn.onclick = function (e) {
      // DOM标准中，是给事件处理函数一个参数
      // e就是事件对象
      // 在老版本的IE中获取事件对象的方式  window.event
      // 处理事件对象的浏览器兼容性
      e = e || window.event;

      // 事件的阶段：1  捕获阶段   2  目标阶段  3 冒泡阶段    了解
      // console.log(e.eventPhase);

      // e.target  获取真正触发事件的对象  浏览器兼容问题
      // 在老版本的IE中  srcElement
      // 处理兼容性问题
      var target = e.target || e.srcElement;
      console.log(e.target);
        
      // e.currentTarget  事件处理函数所属的对象this
      console.log(e.currentTarget);
    }

    var box1 = document.getElementById('box1');
    var box2 = document.getElementById('box2');
    var box3 = document.getElementById('box3');
    var array = [box1, box2, box3];
    for (var i = 0; i < array.length; i++) {
      var box = array[i];
      box.onclick = function (e) {
        e = e || window.event;
        // 事件的阶段
        console.log(e.eventPhase);
        // e.target 获取真正触发事件的对象
        var target = e.target || e.srcElement;
        console.log(target);
        // e.curentTarget   和this一样 获取事件处理函数所属的对象
        console.log(e.currentTarget);
        console.log(this);
      }
    }
  </script>
</body>

</html>
```

- event.bubbles			返回布尔值，指示事件是否是冒泡事件类型
- event.cancelable             返回布尔值，指示事件是否可拥可取消的默认动作。

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    #box1 {
      width: 300px;
      height: 300px;
      background-color: red;
    }

    #box2 {
      width: 200px;
      height: 200px;
      background-color: green;
    }

    #box3 {
      width: 100px;
      height: 100px;
      background-color: blue;
    }
  </style>
</head>

<body>
  <input type="button" value="按钮" id="btn">
  <div id="box1">
    <div id="box2">
      <div id="box3">
      </div>
    </div>
  </div>

  <input type="text" id="input1">
  <script>
    var box1 = document.getElementById('box1');
    var box2 = document.getElementById('box2');
    var box3 = document.getElementById('box3');
    var input1 = document.getElementById('input1');
    var array = [box1, box2, box3];
    for (var i = 0; i < array.length; i++) {
      var box = array[i];
      //冒泡事件类型：click，mousedown，mouseup，keydown，keyup，keypress等
      box.onclick = function (e) {
        e = e || window.event;
        console.log(e);
        // 是否是冒泡事件类型
        console.log(e.bubbles);
        // 是否可拥可取消的默认动作
        console.log(e.cancelable);
      }

    }

    input1.onfocus = function (e) {
      e = e || window.event;
      // 是否是冒泡事件类型
      console.log(e.bubbles);
      // 是否可拥可取消的默认动作
      console.log(e.cancelable);
    }
  </script>
</body>

</html>
```

- event.type 		获取事件类型
- event.timeStamp       返回事件生成的日期和时间。

```js
var box1 = document.getElementById('box1');
var box2 = document.getElementById('box2');
var box3 = document.getElementById('box3');
var input1 = document.getElementById('input1');
var array = [box1, box2, box3];
for (var i = 0; i < array.length; i++) {
    var box = array[i];
    //冒泡事件类型：click，mousedown，mouseup，keydown，keyup，keypress等
    box.onclick = function (e) {
        e = e || window.event;
        // 获取事件类型
        console.log(e.type);
        //   返回事件生成的日期和时间。
        console.log(e.timeStamp)
    }

}

input1.onfocus = function (e) {
    e = e || window.event;
    // 获取事件类型
    console.log(e.type);
    //   返回事件生成的日期和时间。
    console.log(e.timeStamp)
}

// 获取时间类型的作用: 可以给多个事件绑定一个事件函数,提升性能
var box = document.getElementById('box');
// box.onclick = function (e) {
//   e = e || window.event;
//   // 获取事件名称
//   console.log(e.type);
// }

box.onclick = fn;
box.onmouseover = fn;
box.onmouseout = fn;

function fn(e) {
    e = e || window.event;
    switch (e.type) {
        case 'click': 
            console.log('点击box');
            break;
        case 'mouseover': 
            console.log('鼠标经过box');
            break;
        case 'mouseout': 
            console.log('鼠标离开box');
            break;
    }
}
```

- event.clientX/clientY     所有浏览器都支持，窗口位置
- event.pageX/pageY       IE9以前不支持，页面位置

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
      height: 1000px;
    }
    #box {
      margin: 100px;
      margin-top: 500px;
      width: 200px;
      height: 200px;
      background-color: red;
    }
  </style>
</head>
<body>
  <div id="box">
  </div> 
  <script>
    var box = document.getElementById('box');
    box.onclick = function (e) {
      e = e || window.event;

      // 获取的鼠标在浏览器的可视区域的坐标
      // console.log(e.clientX);
      // console.log(e.clientY);

      // 鼠标在当前页面的位置
      console.log(e.pageX);
      console.log(e.pageY);

    }

  </script>
</body>
</html>
```

**pageX和pageY兼容性解决**

​	e.clientX/e.clientY		鼠标在可视区域中的位置

​	e.pageX/e.pageY		鼠标在页面中的位置 有兼容性问题  从IE9以后才支持

​	pageY = clientY + 页面滚动出去的距离

**步骤1:获取页面滚动出去的距离**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      height: 1000px;
    }

    div {
      width: 300px;
      height: 300px;
      background: yellow;
      margin-top: 360px;
    }
  </style>
</head>

<body>
  <div>

  </div>
  <script>
    document.onclick = function () {
      // 输出页面滚动出去的距离
      console.log(document.body.scrollLeft);
      console.log(document.body.scrollTop);

      // documentElement  文档的根元素  html标签
      // console.log(document.documentElement);
      // 有些浏览器 是使用这两个属性来获取的
      console.log(document.documentElement.scrollLeft);
      console.log(document.documentElement.scrollTop);

    }

    // 获取页面滚动距离的浏览器兼容性问题
    // 获取页面滚动出去的距离
    function getScroll() {
      var scrollLeft = document.body.scrollLeft || document.documentElement.scrollLeft;
      var scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
      return {
        scrollLeft: scrollLeft,
        scrollTop: scrollTop
      }
    }
  </script>
</body>

</html>
```

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      height: 1000px;
    }
  </style>
</head>

<body>

  <script>
    // e.clientX/e.clientY   鼠标在可视区域中的位置
    // e.pageX/e.pageY       鼠标在页面中的位置 有兼容性问题  从IE9以后才支持
    // pageY = clientY + 页面滚动出去的距离
    document.onclick = function (e) {
      e = e || window.event;
      console.log(getPage(e).pageX);
      console.log(getPage(e).pageY);

    }

    // 获取鼠标在页面的位置，处理浏览器兼容性
    function getPage(e) {
      var pageX = e.pageX || e.clientX + getScroll().scrollLeft;
      var pageY = e.pageY || e.clientY + getScroll().scrollTop;
      return {
        pageX: pageX,
        pageY: pageY
      }
    }

    // 获取页面滚动距离的浏览器兼容性问题
    // 获取页面滚动出去的距离
    function getScroll() {
      var scrollLeft = document.body.scrollLeft || document.documentElement.scrollLeft;
      var scrollTop = document.body.scrollTop || document.documentElement.scrollTop;
      return {
        scrollLeft: scrollLeft,
        scrollTop: scrollTop
      }
    }
  </script>
</body>

</html>
```

- 修改键

有时，我们需要通过键盘上的某些键来配合鼠标来触发一些特殊的事件。这些键为：Shfit、Ctrl、Alt，它们经常被用来修改鼠标事件和行为，所以叫修改键。

属性			说明

shiftKey			判断是否按下了Shfit 键

ctrlKey			判断是否按下了ctrlKey 键

altKey			判断是否按下了alt 键

**1、判断是否按下alt键、shift键、ctrl键**

```js
document.onkeydown = function (e) {
    if(e.altKey){
        alert("alt按下");
    }else if(e.shiftKey){
        alert("shift按下");
    }else if(e.ctrlKey){
        alert("ctrl按下");
    }else{
        alert("按下的不是alt/shift/ctrl");
    }
}
```

**2、判断alt键、shift键、ctrl键是否同时按下**

```js
document.onkeydown = function (e) {
    if(e.altKey && e.shiftKey ){
        alert("同时按下");
    }
}


document.onkeydown = function (e) {
    if(e.altKey && e.shiftKey && e.ctrlKey){
        alert("同时按下");
    }
}
```

- 键码

在发生keydown 和keyup 事件时，event 对象的keyCode 属性中会包含一个代码，与键盘上一个特定的键对应。对数字字母字符集，keyCode 属性的值与ASCII 码中对应小写字母或数字的编码相同。字母中大小写不影响。

```js
document.onkeydown = function (evt) {
	alert(evt.keyCode); //按任意键，得到相应的keyCode
};

// 在键盘上每个键都有一个keyCode,可以通过如下方法获取每个键对应的keyCode。
document.onkeydown = function (e) {
   alert(e.keyCode);
}

document.onkeypress = function (e) {
   alert(e.keyCode);
}
```

​	Firefox、Chrome和Safari 的event 对象都支持一个charCode 属性，这个属性只有在发生keypress 事件时才包含值，而且这个值是按下的那个键所代表字符的ASCII 编码。此时的keyCode 通常等于0 或者也可能等于所按键的编码。IE 和Opera 则是在keyCode 中保存字符的ASCII 编码。

```js
document.onkeypress = function (e) {
   var key = String.fromCharCode(e.charCode);
    alert(key);
}
```

需要注意的是，可以使用String.fromCharCode()将ASCII 编码转换成实际的字符。

### 2.4.4、事件委托

**什么叫事件委托呢？**

​	JavaScript高级程序设计上讲：事件委托就是利用事件冒泡，只指定一个事件处理程序，就可以管理某一类型的所有事件。

**举例：**

​	有三个同事预计会在周一收到快递。为签收快递，有两种办法：一是三个人在公司门口等快递；二是委托给前台MM代为签收。现实当中，我们大都采用委托的方案（公司也不会容忍那么多员工站在门口就为了等快递）。前台MM收到快递后，她会判断收件人是谁，然后按照收件人的要求签收，甚至代为付款。这种方案还有一个优势，那就是即使公司里来了新员工（不管多少），前台MM也会在收到寄给新员工的快递后核实并代为签收。

**这里其实还有2层意思的：**

第一，现在委托前台的同事是可以代为签收的，即程序中的现有的dom节点是有事件的；

第二，新员工也是可以被前台MM代为签收的，即程序中新添加的dom节点也是有事件的。

**为什么要用事件委托？**

​	一般来说，dom需要有事件处理程序，我们都会直接给它设事件处理程序就好了，那如果是很多的dom需要添加事件处理呢？比如我们有100个li，每个li都有相同的click点击事件，可能我们会用for循环的方法，来遍历所有的li，然后给它们添加事件，那这么做会存在什么影响呢？

​	在JavaScript中，添加到页面上的事件处理程序数量将直接关系到页面的整体运行性能，因为需要不断的与dom节点进行交互，访问dom的次数越多，引起浏览器重绘与重排的次数也就越多，就会延长整个页面的交互就绪时间，这就是为什么性能优化的主要思想之一就是减少DOM操作的原因；如果要用事件委托，就会将所有的操作放到js程序里面，与dom的操作就只需要交互一次，这样就能大大的减少与dom的交互次数，提高性能；

​	每个函数都是一个对象，是对象就会占用内存，对象越多，内存占用率就越大，自然性能就越差了，比如上面的100个li，就要占用100个内存空间，如果是1000个，10000个呢，那只能说呵呵了，如果用事件委托，那么我们就可以只对它的父级（如果只有一个父级）这一个对象进行操作，这样我们就需要一个内存空间就够了，是不是省了很多，自然性能就会更好。

**事件委托的原理：**

​	事件委托是利用事件的冒泡原理来实现的

**事件委托怎么实现：**

```html
<ul id="ul1">
    <li>111</li>
    <li>222</li>
    <li>333</li>
    <li>444</li>
</ul>
```

实现功能是点击li，弹出123：

```js
window.onload = function(){
    var oUl = document.getElementById("ul1");
    var aLi = oUl.getElementsByTagName('li');
    for(var i=0;i<aLi.length;i++){
        aLi[i].onclick = function(){
            alert(123);
        }
    }
}
```

上面的代码的意思很简单，相信很多人都是这么实现的，我们看看有多少次的dom操作，首先要找到ul，然后遍历li，然后点击li的时候，又要找一次目标的li的位置，才能执行最后的操作，每次点击都要找一次li；

那么我们用事件委托的方式做又会怎么样呢？

```js
window.onload = function(){
    var oUl = document.getElementById("ul1");
   oUl.onclick = function(){
        alert(123);
    }
}
```

这里用父级ul做事件处理，当li被点击时，由于冒泡原理，事件就会冒泡到ul上，因为ul上有点击事件，所以事件就会触发，当然，这里当点击ul的时候，也是会触发的，那么问题就来了，如果我想让事件代理的效果跟直接给节点的事件效果一样怎么办，比如说只有点击li才会触发，不怕，我们有绝招：

Event对象提供了一个属性叫target，可以返回事件的目标节点，我们成为事件源，也就是说，target就可以表示为当前的事件操作的dom，但是不是真正操作dom，当然，这个是有兼容性的，标准浏览器用ev.target，IE浏览器用event.srcElement，此时只是获取了当前节点的位置，并不知道是什么节点名称，这里我们用nodeName来获取具体是什么标签名，这个返回的是一个大写的，我们需要转成小写再做比较（习惯问题）：

> 解释var ev = ev || window.event;：https://www.jianshu.com/p/e8a6fad0f7bc

```js
window.onload = function(){
　　var oUl = document.getElementById("ul1");
　　oUl.onclick = function(ev){
　　　　var ev = ev || window.event;
　　　　var target = ev.target || ev.srcElement;
       // 检查事件源e.target是否为Li 
　　　　if(target.nodeName.toLowerCase() == 'li'){
　 　　　　　　 alert(123);
　　　　　　　  alert(target.innerHTML);
　　　　}
　　}
}
```

这样改下就只有点击li会触发事件了，且每次只执行一次dom操作，如果li数量很多的话，将大大减少dom的操作，优化的性能可想而知！

上面的例子是说li操作的是同样的效果，要是每个li被点击的效果都不一样，那么用事件委托还有用吗？

```html
<div id="box">
    <input type="button" id="add" value="添加" />
    <input type="button" id="remove" value="删除" />
    <input type="button" id="move" value="移动" />
    <input type="button" id="select" value="选择" />
</div>
```

```js
window.onload = function(){
    var Add = document.getElementById("add");
    var Remove = document.getElementById("remove");
    var Move = document.getElementById("move");
    var Select = document.getElementById("select");

    Add.onclick = function(){
        alert('添加');
    };
    Remove.onclick = function(){
        alert('删除');
    };
    Move.onclick = function(){
        alert('移动');
    };
    Select.onclick = function(){
        alert('选择');
    }

}
```

上面实现的效果我就不多说了，很简单，4个按钮，点击每一个做不同的操作，那么至少需要4次dom操作，如果用事件委托，能进行优化吗？

```js
window.onload = function(){
    var oBox = document.getElementById("box");
    oBox.onclick = function (ev) {
        var ev = ev || window.event;
        var target = ev.target || ev.srcElement;
        if(target.nodeName.toLocaleLowerCase() == 'input'){
            switch(target.id){
                case 'add' :
                    alert('添加');
                    break;
                case 'remove' :
                    alert('删除');
                    break;
                case 'move' :
                    alert('移动');
                    break;
                case 'select' :
                    alert('选择');
                    break;
            }
        }
    }

}
```

用事件委托就可以只用一次dom操作就能完成所有的效果，比上面的性能肯定是要好一些的 

现在讲的都是document加载完成的现有dom节点下的操作，那么如果是新增的节点，新增的节点会有事件吗？也就是说，一个新员工来了，他能收到快递吗？

看一下正常的添加节点的方法：

```html
<input type="button" name="" id="btn" value="添加" />
<ul id="ul1">
    <li>111</li>
    <li>222</li>
    <li>333</li>
    <li>444</li>
</ul>
```

现在是移入li，li变红，移出li，li变白，这么一个效果，然后点击按钮，可以向ul中添加一个li子节点

```js
window.onload = function(){
    var oBtn = document.getElementById("btn");
    var oUl = document.getElementById("ul1");
    var aLi = oUl.getElementsByTagName('li');
    var num = 4;

    //鼠标移入变红，移出变白
    for(var i=0; i<aLi.length;i++){
        aLi[i].onmouseover = function(){
            this.style.background = 'red';
        };
        aLi[i].onmouseout = function(){
            this.style.background = '#fff';
        }
    }
    //添加新节点
    oBtn.onclick = function(){
        num++;
        var oLi = document.createElement('li');
        oLi.innerHTML = 111*num;
        oUl.appendChild(oLi);
    };
}
```

这是一般的做法，但是你会发现，新增的li是没有事件的，说明添加子节点的时候，事件没有一起添加进去，这不是我们想要的结果，那怎么做呢？一般的解决方案会是这样，将for循环用一个函数包起来，命名为mHover，如下：

```js
window.onload = function(){
    var oBtn = document.getElementById("btn");
    var oUl = document.getElementById("ul1");
    var aLi = oUl.getElementsByTagName('li');
    var num = 4;

    function mHover () {
        //鼠标移入变红，移出变白
        for(var i=0; i<aLi.length;i++){
            aLi[i].onmouseover = function(){
                this.style.background = 'red';
            };
            aLi[i].onmouseout = function(){
                this.style.background = '#fff';
            }
        }
    }
    mHover ();
    //添加新节点
    oBtn.onclick = function(){
        num++;
        var oLi = document.createElement('li');
        oLi.innerHTML = 111*num;
        oUl.appendChild(oLi);
        mHover ();
    };
}
```

虽然功能实现了，看着还挺好，但实际上无疑是又增加了一个dom操作，在优化性能方面是不可取的，那么有事件委托的方式，能做到优化吗？

```js
window.onload = function(){
    var oBtn = document.getElementById("btn");
    var oUl = document.getElementById("ul1");
    var aLi = oUl.getElementsByTagName('li');
    var num = 4;

    //事件委托，添加的子元素也有事件
    oUl.onmouseover = function(ev){
        var ev = ev || window.event;
        var target = ev.target || ev.srcElement;
        if(target.nodeName.toLowerCase() == 'li'){
            target.style.background = "red";
        }

    };
    oUl.onmouseout = function(ev){
        var ev = ev || window.event;
        var target = ev.target || ev.srcElement;
        if(target.nodeName.toLowerCase() == 'li'){
            target.style.background = "#fff";
        }

    };

    //添加新节点
    oBtn.onclick = function(){
        num++;
        var oLi = document.createElement('li');
        oLi.innerHTML = 111*num;
        oUl.appendChild(oLi);
    };
}
```

看，上面是用事件委托的方式，新添加的子元素是带有事件效果的，我们可以发现，当用事件委托的时候，根本就不需要去遍历元素的子节点，只需要给父级元素添加事件就好了，其他的都是在js里面的执行，这样可以大大的减少dom操作，这才是事件委托的精髓所在。

适合用事件委托的事件：click，mousedown，mouseup，keydown，keyup，keypress。

值得注意的是，mouseover和mouseout虽然也有事件冒泡，但是处理它们的时候需要特别的注意，因为需要经常计算它们的位置，处理起来不太容易。

不适合的就有很多了，举个例子，mousemove，每次都要计算它的位置，非常不好把控，在不如说focus，blur之类的，本身就没用冒泡的特性，自然就不能用事件委托了。

### 2.4.5、阻止事件

​       event.stopPropagation()方法阻止事件在 DOM 中继续传播，防止再触发定义在别的节点上的监听函数，但是不包括在当前节点上其他的事件监听函数。

```js
function stopEvent(e) {
  // 标准的DOM方法
  e.stopPropagation();
    
  // 取消冒泡  非标准的方式 老版本的IE支持
  e.cancelBubble = true;
}

el.addEventListener('click', stopEvent, false);
```

​       上面代码中，click事件将不会进一步冒泡到el节点的父节点。

```js
//阻止事件冒泡的兼容写法
function stopBubble(e){
    //如果提供了事件对象，则是一个非IE浏览器
    if(e && e.stopPropagation)
        //因此它支持W3C的stopPropagation()方法
        e.stopPropagation();
    else
        //否则，我们需要使用IE的方式来取消事件冒泡
        window.event.cancelBubble = true;
}
```

​	event.preventDefault()方法取消浏览器对当前事件的默认行为这是阻止默认事件的方法，调用此方法是，连接不会被打开，但是会发生冒泡，冒泡会传递到上一层的父元素；

​	比如点击链接后，浏览器默认会跳转到另一个页面，使用这个方法以后，就不会跳转了；

​	该方法生效的前提是，事件对象的cancelable属性为true，如果为false，调用该方法没有任何效果。

​	阻止事件冒泡的方法，其中e是function中的参数；

```html
<input type="checkbox" id="my-checkbox" />

<script>
    var cb = document.getElementById('my-checkbox');
    cb.addEventListener(
        'click',
        function (e) {
            // DOM标准方法
            e.preventDefault();

            // IE的老版本，非标准方式
      		e.returnValue = false;
        },
        false
    );
</script>
```

​	上面代码中，浏览器的默认行为是单击会选中单选框，取消这个行为，就导致无法选中单选框。

​	return false,这个方法也会阻止默认事件;

```html
<div id="div1">
    <a href="http://www.baidu.com" id="myA">我是超链接</a>
</div>

<script>
    var myA = document.getElementById('myA');
    var div1 = document.getElementById("div1");
    div1.onclick = function () {
        alert("div1触发了事件");
    }

    myA.onclick = function () {
        return false;
    }
</script>
```

```js
//阻止事件默认行为的兼容写法
function stopDefault(e){
    //如果提供了事件对象，则是一个非IE浏览器
    if(e && e.preventDefault)
        //因此它支持W3C的preventDefault()方法
        e.preventDefault();
    else
        //否则，我们需要使用IE的方式来取消事件默认行为
        window.event.returnValue = false;
}
```

## 2.5、事件流

​        很久以前有个叫Netscape的姑娘，她制订了Javascript的一套事件驱动机制（即事件捕获）。后来又有一个叫“IE”的小子，这孩子比较傲气，他认为“凭什么我要依照你的规则走”，于是他又创造了一套自己的规则（事件冒泡）。再后来，有个叫W3C的媒婆，想撮合这两个孩子，将他们的特点融合在了一起，这下，事件产生的顺序变成：事件从根节点开始，逐级派送到子节点，若节点绑定了事件动作，则执行动作，然后继续走，这个阶段称为“捕获阶段(Capture)”；执行完捕获阶段后，事件由子节点往根节点派送，若节点绑定了事件动作，则执行动作，然后继续走，这个阶段称为“冒泡阶段(Bubble)”。

​        **事件流是描述的从页面接受事件的顺序**，当几个都具有相同事件的元素层叠在一起的时候，比如点击事件,那么你点击其中一个元素，并不是只有当前被点击的元素会触发事件，而层叠在你点击范围的所有元素都会触发事件。**事件流包括两种模式：冒泡和捕获(捕捉)**。

​        事件冒泡，是从里往外逐个触发。事件捕获，是从外往里逐个触发。**那么现代的浏览器默认情况下都是冒泡模型，而捕获模式则是早期的Netscape 默认情况**。

​        当我们在 DOM 树的某个节点发生了一些操作（例如单击、鼠标移动上去），就会有一个事件发射过去。这个事件从 Window 发出，不断经过下级节点直到目标节点。在到达目标节点之前的过程，就是捕获阶段（Capture Phase）。所有经过的节点，都会触发这个事件。捕获阶段的任务就是建立这个事件传递路线，以便后面冒泡阶段顺着这条路线返回 Window。

​        监听某个在捕获阶段触发的事件，需要在事件监听函数传递第三个参数 true。

![1573104923299](images04_dom/1573104923299.png)

## 2.6、案例

- **跟着鼠标飞的天使**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      height: 1000px;
    }
    #ts {
      position: absolute;
    }
  </style>
</head>
<body>
  <img src="images/tianshi.gif" id="ts" alt="">
  <script>
    var ts = document.getElementById('ts');
    document.onmousemove = function (e) { 
      e = e || window.event;
      // ts.style.left = e.clientX - 10 + 'px';
      // ts.style.top = e.clientY - 10 + 'px';

      ts.style.left = e.pageX - 10 + 'px';
      ts.style.top = e.pageY - 10 + 'px';
    }
  </script>
</body>
</html>
```

- **只能输入数值**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <script>
    
  </script>
</head>
<body>
  <input id="txt" type="text">
  <script>
    // 键盘事件
    // keydown 键盘按下的时候
    // keyup   键盘弹起的时候
    // keydown 和 keyup的区别  keydown的时候我们所按的键还没有落入文本框
    // keyup键盘弹起的时候按的键已经落入文本框
    var txt = document.getElementById('txt');
    txt.onkeydown = function (e) {
      // 判断当前用户按下的键是否是数字
      e = e || window.event;

      // 如果e.keyCode 的值在 48-57 是数字
      // e.keyCode  键盘码
      // console.log(e.keyCode);
      // 按下后退键  8，删除一个字符 
      if ((e.keyCode < 48 || e.keyCode > 57) && e.keyCode !== 8) {
        // 非数字
        // 取消默认行为
        e.preventDefault();
        // return false;
      }

    }
  </script>
</body>
</html>
```

<a id="p5-3"></a>
# 三、JavaScript操作CSS样式

## 3.1、使用style操作样式(重点)

### 3.1.1、使用规则

​        任何HTML元素标签都会有一个通用的属性：style,它会返回CSSStyleDeclaration对象。其语法格式为HTML元素.style.样式属性＝"值"。但是需要注意的是，JavaScript样式属性的写法和CSS写法有点不同，比如字体的大小，CSS代码为font-size,而JavaScript的代码为fontSize。

​        以下两张表格都是JavaScript写样式属性的，注意和CSS代码的区别。

![1573192561359](images04_dom/1573192561359.png)

![1573192598031](images04_dom/1573192598031.png)

**注意:通过样式属性设置宽高、位置的属性类型是字符串，需要加上px**

### 3.1.2、简单动画案例

**效果1:点击改变div的颜色,再次点击返回原样:**

![1573192623745](images04_dom/1573192623745.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        #div1 {
            width: 200px;
            height: 200px;
            background: yellow;
        }
    </style>
</head>

<body>
    <div id="div1">

    </div>
    <script>
        // 获取div1元素节点
        var div1 = document.getElementById("div1");

        var flag = 1; // 如果是1的时候,代表的黄色,要变为红色
        div1.onclick = function () {
            if (flag === 1) {
                div1.style.background = "red";
                flag = 2; //改变flag的值
            } else {
                div1.style.background = "yellow";
                flag = 1; //改变flag的值
            }
        }
    </script>
</body>

</html>
```

**效果2:鼠标移入列表改变背景图片,移出恢复原样:**

![1573192691578](images04_dom/微信截图_20200722134758.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        ul,
        li {
            padding: 0;
            margin: 0;
        }

        ul {
            list-style: none;
            font-size: 12px;
            color: blue;
        }

        li {
            display: inline-block;
            width: 87px;
            height: 30px;
            line-height: 30px;
            text-align: center;
            user-select: none;
            cursor: pointer;
            background: url("images/5.png");
        }

        /* li:hover {
            background: url("images/3.png");
        } */
    </style>
</head>

<body>
    <ul id="ul1">
        <li>首 页</li>
        <li>水果生鲜</li>
        <li>牛奶饮品</li>
        <li>帮助中心</li>
        <li>关于我们</li>
    </ul>
    <script>
        var ul1 = document.getElementById("ul1");
        ul1.onmouseover = function (e) {
            e = e || window.event;
            var target = e.target || e.srcElement;

            if (target.nodeName.toLowerCase() === 'li') {
                console.log("点击了" + target.innerHTML); // target就是元素节点
                // console.log(target.style); // CSSStyleDeclaration
                // css样式写的是什么值,现在通过js来进行操作的也应是什么值
                target.style.background = 'url("images/3.png")';
            }
        }

        ul1.onmouseout = function (e) {
            e = e || window.event;
            var target = e.target || e.srcElement;

            if (target.nodeName.toLowerCase() === 'li') {
                console.log("点击了" + target.innerHTML); // target就是元素节点
                // console.log(target.style); // CSSStyleDeclaration
                // css样式写的是什么值,现在通过js来进行操作的也应是什么值
                target.style.background = 'url("images/5.png")';
            }
        }
    </script>
</body>

</html>
```

### 3.1.3、CSSStypeDeclaration的属性和方法

​        正如上面提到的，HTML元素.style返回的是返回CSSStypeDeclaration对象，该对象中定义了一些属性和方法，可以在JavaScript中操作HTML元素的样式。

| 属性或方法               | 说明                              |
| ------------------------ | --------------------------------- |
| cssText                  | 访问或设置CSS 代码                |
| length                   | 获取样式属性的数量                |
| getPropertyValue(name)   | 返回包含给定属性值的CSSValue 对象 |
| item(index)              | 返回指定位置CSS 属性名称          |
| **removeProperty(name)** | **从样式中删除指定属性**          |
| setProperty(name,v)      | 给属性设置为相应的值              |

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        #div1 {
            width: 300px;
            height: 200px;
            background-color: yellow;
        }
    </style>
</head>

<body>

    <div id="div1" style="font-size: 12px;color:green;border: 1px solid black;">
        我是div的文本内容
    </div>

    <script>
        // 获取得到div1元素节点
        var div1 = document.getElementById("div1");

        // 元素节点.style   ->CSSStyleDeclaration
        console.log(div1.style);

        var cssStyleDec = div1.style;

        // cssText      访问或设置CSS 代码
        // 获取得到行内样式
        console.log("cssText代码:" + cssStyleDec.cssText);

        // 三次dom操作
        // cssStyleDec.fontSize = "20px";
        // cssStyleDec.color = "hotpink";
        // cssStyleDec.border = "3px solid blue";


        // 结合今天上午讲的内容,好好想一下? 
        // cssStyleDec.cssText = "font-size: 20px;color:hotpink;border: 1px solid blue;";

        // 一次性设置多个样式,可以怎么办? 通过className属性替换类

        // 获取样式属性的数量
        // console.log("样式属性的数量:" + cssStyleDec.length)

        // getPropertyValue(name)   返回包含给定属性值的CSSValue 对象
        console.log("div1的字体颜色:" + cssStyleDec.getPropertyValue("color"));
        console.log("div1的字体颜色:" + cssStyleDec.color);

        // 两者都是可以获取到行内样式的值,但是第一种方式对于-分割的样式,必须去除中划线,中划线后面的首字母大小
        console.log("div1的字体颜色:" + cssStyleDec.fontSize);
        // 第二种方式,可以使用css样式属性名
        console.log("div1的字体大小:" + cssStyleDec.getPropertyValue("font-size"));

        // item(index) 返回指定位置CSS 属性名称
        console.log("-------------------------------");
        for (var i = 0; i < cssStyleDec.length; i++) {
            console.log(cssStyleDec[i]);
        }

        // removeProperty(name) 从样式中删除指定属性
        cssStyleDec.removeProperty("color");


        cssStyleDec.setProperty("color", "skyblue");

        cssStyleDec.color = "red";
    </script>
</body>

</html>
```

## 3.2、使用className访问样式

​        除了使用HTML元素.style.样式属性＝"值"来访问元素的样式外，这种方法只能对元素的样式一个一个的访问，如果样式设置比较多，就比较繁琐。还可以使用HTML元素.className=’类样式名’来设置元素的样式，这时可以把多个样式写在同一个类样式中。

​        **案例: 用className实现菜单制作:**

​        实现思路：
​        1、设置每一个li标签的初始状态。
​        2、设置两个样式over和out，表示鼠标移至菜单和移出菜单的效果。
​        3、统一为每一个li标签设置onmouseover事件和onmouseout事件效果

![1573193051509](images04_dom/1573193051509.png)

![1573193056959](images04_dom/1573193056959.png)

## 3.3、操作内部或外部CSS样式(了解)

​        之前我们使用style 属性，仅仅只能获取和设置行内的样式，如果是通过内联```<style>```或链接```<link>```提供的样式规则就无可奈何了，CSSStyleSheet 类型表示通过```<link>```元素和```<style>```元素包含的样式表。

```js
通过代码document.getElementsByTagName('link')[0]; 获取一个HTMLLinkElement对象;

通过document.getElementsByTagName('style')[0];获取一个HTMLStyleElement。

这两个元素本身返回的是HTMLLinkElement 和HTMLStyleElement 类型，但CSSStyleSheet 类型更加通用一些。

通过sheet属性,可以把 HTMLLinkElement 和 HTMLStyleElement 对象转换为CSSStyleSheet 类型
```

​        **常见CSSStyleSheet属性和方法:**

| 属性或方法              | 说明                                                         |
| ----------------------- | ------------------------------------------------------------ |
| disabled                | 获取和设置样式表是否被禁用                                   |
| cssRules                | 样式表包含样式规则的集合                                     |
| deleteRule(index)       | 删除cssRules 集合中指定位置的规则                            |
| insertRule(rule, index) | 向cssRules 集合中指定位置插入rule 字符串，IE也可以用addRule(选择器名, 属性名:属性值, 索引) |

```js
var img1=document.getElementById("img");

var link = document.getElementsByTagName('link')[0];

var sheet = link.sheet || link.styleSheet; //得到CSSStyleSheet

sheet.insertRule("body {background-color:red}", 2);

link.sheet.deleteRule(2);
```

​        通过CSSRules 属性，我们可以获得样式表的规则集合列表。这样我们就可以对每个样式进行具体的操作了。

​        通过cssRules[下标值]可以获取一个CSSStyleRule对象，通过访问CSSStyleRule对象来操作样式。

​        **CSSStyleRule常用属性:**

| 属性         | 说明                                             |
| ------------ | ------------------------------------------------ |
| cssText      | 获取当前整条规则对应的文本，IE 不支持            |
| selectorText | 获取当前规则的选择符文本                         |
| style        | 返回CSSStyleDeclaration 对象，可以获取和设置样式 |

```js
rule.cssText; //当前规则的样式文本
rule.selectorText; //#box，样式的选择符
rule.style.color; //red，得到具体样式值
```

**通过计算属性操作样式**

```js
//精准操作内部和外部css样式 [这种方式就是获取到作用域元素的样式,然后再去操作]

//1. 获取到要操作样式的元素节点
var div1 = document.getElementById("div1"); //获取到div1元素节点

//2. 获取到作用与div1的所有样式 CSSStyleDecalaration
var div1Style = getComputedStyle(div1);   //window.getComputedStyle(元素节点)   获取到作用于这个元素节点的样式    
            
//只能获取到作用于元素的样式
document.write("div1的宽:"+div1Style.width+"<br>");
document.write("div1的字体大小:"+div1Style.fontSize+"<br>");

 // div1Style.width = "500px";
```

## 3.4、案例

**设置div的大小和位置**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    #box {
      width: 100px;
      height: 100px;
      background-color: pink;
    }

    .cls {
      width: 200px;
      height: 200px;
      position: absolute;
      top: 100px;
      left: 100px;
      background-color: pink;
    }
  </style>
</head>
<body>
  <input type="button" value=" 点我 " id="btn">
  <br>
  <div id="box"></div>
  <script>
  	 btn.onclick = function () {
      // 改变box的大小和位置
      // 使用class
      // box.className = 'cls';
      // 
      // 使用style  设置大小和位置的时候 数字必须带单位
      box.style.width = '200px';
      box.style.height = '200px';

      box.style.position = 'absolute';
      box.style.left = '200px';
      box.style.top = '200px';

      console.log(box.style);
    }

  </script>
</body>
</html>
```

**div显示或隐藏**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>Document</title>
    <style>
        #box {
            width: 200px;
            height: 200px;
            background-color: red;
        }
    </style>
</head>

<body>
    <input type="button" value=" 点我 " id="btn">
    <br>
    <div id="box"></div>
    <script>
        // 获取得到页面元素节点
        var btn = document.getElementById("btn");
        var box = document.getElementById("box");
        var flag = 1;
        var boxHeight = 200;
        var boxOpacity = 1;

        // 隐藏的时候: 高度逐渐变为0,并且透明度变为0
        // 1500ms
        btn.onclick = function () {
            if (flag === 1) { // 隐藏
                // box.style.display = "none";
                var interId = setInterval(function () {
                    // 不能使用boxHeight / 30
                    boxHeight = boxHeight - 200 / 30;
                    boxOpacity = boxOpacity - 1 / 30;
                    box.style.height = boxHeight + "px";
                    box.style.opacity = boxOpacity;
                    if (boxHeight <= 0 || boxOpacity <= 0) {
                        box.style.opacity = 0;
                        box.style.height = "0px";

                        clearInterval(interId);
                    }
                }, 10)
                flag = 2;
            } else { // 显示
                // box.style.display = "block";
                var interId = setInterval(function () {
                    // 不能使用boxHeight / 30
                    boxHeight = boxHeight + 200 / 30;
                    boxOpacity = boxOpacity + 1 / 30;
                    box.style.height = boxHeight + "px";
                    box.style.opacity = boxOpacity;
                    if (boxHeight >= 200 || boxOpacity >= 1) {
                        box.style.opacity = 1;
                        box.style.height = "200px";

                        clearInterval(interId);
                    }
                }, 10)
                flag = 1;
            }
        }
    </script>
</body>

</html>
```

**开关灯**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
</head>
<body>
  <input type="button" value="关灯" id="btn">
    
  <script>
    // 是否开灯  false 关灯状态  true 开灯状态
    var isOpen = true;
    btn.onclick = function () {
      if (isOpen) {
        document.body.style.backgroundColor = 'black';
        this.value = '开灯';
        isOpen = false;
      } else {
        document.body.style.backgroundColor = 'white';
        this.value = '关灯';
        isOpen = true;
      }
    }
  </script>
  
</body>
</html>
```

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>灯控页面</title>
    <script src="js/jquery.min.js">
    </script>
    <style>
        * {
            padding: 0;
            margin: 0;
        }

        /*灯控页面的所有样式代码*/
        /*给body设置背景图片,背景图片居中显示,左右平铺*/
        /*url("../images/bg.jpg")  找背景图片
  center 0      水平居中,上下靠顶部
  repeat-x      水平平铺
*/
        body {
            background: #404040 url("images/bg.jpg") center 0 repeat-x;
        }

        /*选择titleDiv元素*/
        .titleDiv {
            font-size: 24px;
            /*设置字体大小*/
            font-weight: bold;
            /*设置字体粗体*/
            color: yellow;
            /*设置字体颜色*/
            margin: 30px 0 -5px 270px;
            /*设置元素的外边距*/
        }

        /*选择lampDiv元素*/
        .lampDiv {
            width: 340px;
            /*设置宽度*/
            height: 520px;
            /*设置高度*/
            margin: 0 auto;
            /*设置左右居中*/
        }

        /*选择lampBtmDiv元素*/
        .lampBtmDiv {
            width: 366px;
            /*设置宽度*/
            height: 212px;
            /*设置高度*/
            background: url("images/light_btm_bg.png");
            /*设置背景图片*/
            margin: -80px auto 0;
            position: relative;
            /*给该元素设置定位属性,为了可以设置z轴的关系*/
            z-index: 2;
            text-align: center;
        }

        /*选择lampBtmDiv下面的img元素*/
        .lampBtmDiv>img {
            margin-top: 25px;
            /*这里可以通过外边距让元素居中,但是不能用auto*/
            cursor: pointer;
        }

        /*选择colorBtnDiv元素*/
        .colorBtnDiv {
            width: 430px;
            /*设置宽度*/
            height: 66px;
            /*设置高度*/
            margin: -27px auto 0;
            /*设置居中*/
            position: relative;
            /*给该元素设置定位属性,为了可以设置z轴的关系*/
            z-index: 3;
        }

        .colorBtnDiv>img {
            cursor: pointer;
        }

        /*分别调整第二张到第五张图片的位置*/
        .twoImg {
            margin-left: 27px;
        }

        .threeImg {
            margin-left: 23px;
        }

        .fourImg {
            margin-left: 19px;
        }

        .fiveImg {
            margin-left: 20px;
        }

        /*选择textTips*/
        .textTips {
            text-align: center;
            margin: 35px 0;
            color: #8B978F;
            font-weight: bold;
        }

        /*设置进度框样式*/
        .progress {
            width: 525px;
            height: 30px;
            background: #101823;
            margin: 0 auto;
            border-radius: 8px;
            box-shadow: 0 0 1px 2px #171D22;
        }

        /*设置btnListDiv的样式*/
        .btnListDiv {
            text-align: center;
            margin: 25px 0 35px;
        }

        /*设置所有的亮度按钮样式*/
        .btnListDiv>button {
            padding: 5px 13px;
            margin: 0 5px;
            border-radius: 5px;
            cursor: pointer;
        }

        /*进度条*/
        .progress-bar {
            height: 100%;
            border-radius: 8px;
        }
    </style>
</head>

<body>
    <!--标题内容-->
    <div class="titleDiv">
        智能家居灯控系统
    </div>


    <!--定义灯泡-->
    <div class="lampDiv">
        <img src="images/l-close.png" alt="">
    </div>

    <!--定义灯的底座-->
    <div class="lampBtmDiv">
        <!--lampStatus="closed" 的作用是为了让程序员自身知道是开灯还是关灯;-->
        <img src="images/switch-close.png" alt="" title="点击开关" lampStatus="closed">
    </div>

    <!--定义颜色按钮区域-->
    <div class="colorBtnDiv">
        <!--顺序是红 黄 蓝 绿 紫-->
        <img src="images/off-red.png" alt="" class="oneImg">
        <img src="images/off-yellow.png" alt="" class="twoImg">
        <img src="images/off-blue.png" alt="" class="threeImg">
        <img src="images/off-green.png" alt="" class="fourImg">
        <img src="images/off-purple.png" alt="" class="fiveImg">
    </div>

    <!--定义文本提示-->
    <div class="textTips">
        点击开关开启;点击下边颜色按钮可以换色!
    </div>


    <!--定义页面动态效果的代码-->
    <script>
        /*获取到开关按钮图片元素*/
        var onOffImgBtn = $(".lampBtmDiv>img");

        /*获取到灯泡图片元素*/
        var lampImg = $(".lampDiv>img");

        /*获取到五个颜色按钮*/
        var allColorBtns = $(".colorBtnDiv>img");

        /*获取到进度条*/
        var progressBar = $(".progress-bar");

        /*获取到所有的亮度按钮*/
        var allLightBtns = $(".btnListDiv>button");

        /* 获取要操作设备的IP */
        var ip = $("#ip").val(); /* 获取到ip的值 */

        /* 获取灯开关状态的值 */
        var lampOnOff = $("#lampOnOff").val();

        if (lampOnOff == "11") {
            var lampLight = $("#lampLight").val();
            onOffImgBtn.attr("src", "images/switch-red.png");
            lampImg.attr("src", "images/l-red.png");
            $(".oneImg").attr("src", "images/on-red.png");
            onOffImgBtn.attr("lampStatus", "open");

        }

        /*给开关按钮图片添加单击事件,当我们点击图片的时候要让他做某些事情,这是代码写在function的{}*/
        onOffImgBtn.click(function () {
            /*这里写单击事件触发的时候,要做的事情
             * 每次触发点击的时候,都要获取lampStatus的值,判断是开灯还是关灯
             * */
            /*我们通过获取图片自定义属性lampStatus的值来判断到底是开灯还是关灯*/
            /*改变onOffImgBtn图片的路径,只需要改变onOffImgBtn元素的src属性的值*/
            var lampStatus = onOffImgBtn.attr("lampStatus");
            if (lampStatus == "closed") {
                onOffImgBtn.attr("src", "images/switch-red.png");
                lampImg.attr("src", "images/l-red.png");
                $(".oneImg").attr("src", "images/on-red.png");

                /*设置进度条100%,颜色为红色*/
                progressBar.css("width", "100%");
                progressBar.css("background", "red");

                /*设置状态为开灯*/
                onOffImgBtn.attr("lampStatus", "open");


            } else {
                onOffImgBtn.attr("src", "images/switch-close.png");
                lampImg.attr("src", "images/l-close.png");
                //调用关闭所有颜色按钮的函数
                closeAllBtns();

                progressBar.css("width", "0");

                /*设置状态为关灯*/
                onOffImgBtn.attr("lampStatus", "closed");

            }
        });


        /*自定义一个数组,来保存颜色值:必须和图片的颜色名称一致*/
        var colorArr = ["red", "yellow", "blue", "green", "purple"];


        /*给五个颜色按钮添加点击事件*/
        /*allColorBtns 本质是一个数组   [红色按钮元素,黄色按钮元素,蓝色按钮元素,绿色按钮元素,紫色按钮元素]*/
        allColorBtns.click(function () {
            /*必须是开灯状态才可以调节灯的颜色*/
            /*如果不是开灯状态,则警告框提示;如果是开灯状态,则调节颜色*/
            var lampStatus = onOffImgBtn.attr("lampStatus"); /*灯的状态*/
            if (lampStatus == "closed") {
                alert("必须是开灯状态才能调节灯的颜色,请开灯!");
            } else {
                /*点击哪个颜色按钮,则哪个颜色按钮变为on-xxx.png,其他颜色按钮都是off-xxx.png*/
                /*获取点击元素的下标*/
                var index = $(this).index();

                //调用关闭所有颜色按钮的函数
                closeAllBtns();

                /*从allColorBtns数组里面获取到要改为on-xxx.png的元素*/
                allColorBtns.eq(index).attr("src", "images/on-" + colorArr[index] + ".png");
                onOffImgBtn.attr("src", "images/switch-" + colorArr[index] + ".png");
                lampImg.attr("src", "images/l-" + colorArr[index] + ".png");
            }
        });


        /*定义一个函数,用来关闭所有的颜色按钮,提高代码重用率*/
        function closeAllBtns() {
            /*先把所有的颜色按钮都改为关闭状态*/
            for (var i = 0; i < allColorBtns.length; i++) {
                /*循环获取每个数组里面的元素*/
                allColorBtns.eq(i).attr("src", "images/off-" + colorArr[i] + ".png");
            }
        }
    </script>
</body>

</html>
```

**点击菜单项切换选中状态**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Title</title>
  <style>
    #menu ul li {
      list-style-type: none;
      line-height: 30px;
      background-color: beige;
      text-align: center;
      float: left;
      margin-left: 5px;
    }

    #menu ul li.current {
      background-color: burlywood;
    }

    #menu ul li a {
      display: inline-block;
      width: 80px;
      height: 30px;
      text-decoration: none;
    }
  </style>
</head>

<body>
  <div id="menu">
    <ul>
      <li class="current"><a href="javascript:void(0)">首页</a></li>
      <!--<li><a href="javascript:undefined">博客</a></li>-->
      <li><a href="javascript:void(0)">博客</a></li>
      <li><a href="javascript:void(0)">相册</a></li>
      <li><a href="javascript:void(0)">关于</a></li>
      <li><a href="javascript:void(0)">帮助</a></li>
    </ul>
  </div>

  <script>
    // void 是运算符   
    // 执行void后面的表达式，并始终返回undefined

    var menu = document.getElementById("menu");
    // 获取menu中的ul
    var ul = menu.firstElementChild;

    for (var i = 0; i < ul.children.length; i++) {
      var li = ul.children[i];
      // 获取li中的a标签
      var link = li.firstElementChild;
      // 注意：此时是把函数赋给onclick 而不是函数的调用
      link.onclick = linkClick;
    }

    function linkClick() {
      // 所有的li取消高亮显示 
      for (var i = 0; i < ul.children.length; i++) {
        var li = ul.children[i];
        li.className = '';
      }

      // 让当前a标签所在的li高亮显示
      // 
      // this是当前点击的a标签对应的元素
      this.parentNode.className = 'current';

      // 取消后续内容的执行
      return false;
    }
  </script>
</body>

</html>
```

**动态生成列表**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
</head>

<body>
  <input type="button" value="按钮" id="btn">
  <div id="box"></div>

  <script>
    var datas = ['西施', '貂蝉', '凤姐', '芙蓉姐姐'];

    var box = document.getElementById("box");
    // 点击按钮 动态创建列表，鼠标放上高亮显示
    var btn = document.getElementById("btn");

    btn.onclick = function () {
      // 动态创建ul，内存中创建对象
      var ul = document.createElement('ul');
      // 把ul 放到页面上    把ul放到DOM树上，并且会重新绘制
      box.appendChild(ul);

      for (var i = 0; i < datas.length; i++) {
        var data = datas[i];
        // 在内存中动态创建li
        var li = document.createElement('li');
        // 把li添加到DOM树，并且会重新绘制
        ul.appendChild(li);
        // 设置li中显示的内容
        // li.innerText = data;
        setInnerText(li, data);

        // 给li注册事件
        li.onmouseover = liMouseOver;
        li.onmouseout = liMouseOut;
      }
    }
    // 当鼠标经过li的时候执行
    function liMouseOver() {
      // 鼠标经过高亮显示
      this.style.backgroundColor = 'red';
    }

    function liMouseOut() {
      // 鼠标离开取消高亮显示
      this.style.backgroundColor = '';
    }

    // 设置标签之间的内容
    function setInnerText(element, content) {
      // 判断当前浏览器是否支持 innerText
      if (typeof element.innerText === 'string') {
        element.innerText = content;
      } else {
        element.textContent = content;
      }
    }
  </script>
</body>

</html>
```

<a id="p5-4"></a>
# 四、offset、client、scroll三大家

## 4.1、偏移量

- offsetParent用于获取定位的父级元素
- offsetParent和parentNode的区别

![1498743216279](images04_dom/1498743216279.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
    }

    #box {
      /* position: relative; */
      width: 300px;
      height: 300px;
      background-color: red;
      /* 解决顶部外边距问题 */
      overflow: hidden;
      margin: 50px;
    }

    #child {
      width: 100px;
      height: 100px;
      background-color: blue;
      margin: 50px;
      border: 10px solid yellow;
      padding: 10px;
    }
  </style>
</head>

<body>
  <div id="box">
    <div id="child">

    </div>
  </div>

  <script>
    // 3组和大小 位置相关的属性
    // offset  client  scroll
    // 
    // offset  偏移量
    var box = document.getElementById('box');
    // 获取box的坐标
    console.log(box.offsetLeft);
    console.log(box.offsetTop);
    // 获取box的大小
    console.log(box.offsetWidth);
    console.log(box.offsetHeight);

    console.log("----------------")

    // offsetParent   获取距离当前元素最近的定位父元素，如果没有定位父元素此时是body

    // 获取子元素的位置和大小
    var child = document.getElementById('child');
    console.log(child.offsetParent);
    // 获取child的位置     offsetLeft 距离offsetParent的横向偏移
    console.log(child.offsetLeft);
    console.log(child.offsetTop);

    // 获取child的大小   包括边框和padding
    console.log(child.offsetWidth);
    console.log(child.offsetHeight);
  </script>
</body>

</html>
```

## 4.2、客户区大小

![1504075813134](images04_dom/1504075813134.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
    }

    #box {
      width: 100px;
      height: 100px;
      margin: 50px;
      border: 30px solid red;
      padding: 10px;
      background-color: green;
    }
  </style>
</head>

<body>
  <div id="box">

  </div>
  <script>
    // client
    var box = document.getElementById('box');
    // clientLeft  是border-left 的宽度
    // clientTop    border-top 的宽度
    console.log(box.clientLeft);
    console.log(box.clientTop);


    // 获取大小   包括padding  但是不包括边框
    console.log(box.clientWidth);
    console.log(box.clientHeight);

    // offsetWidth   offsetHeight     包括padding和边框
  </script>
</body>
</html>
```

## 4.3、滚动偏移

![1498743288621](images04_dom/1498743288621.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
    }

    #box {
      width: 100px;
      height: 100px;
      margin: 50px;
      border: 30px solid red;
      padding: 10px;
      background-color: green;
      overflow: auto;
    }
  </style>
</head>

<body>
  <div id="box">
    超文本是一种组织信息的方式，它通过超级链接方法将文本中的文字、图表与其他信息媒体相关联。这些相互关联的信息媒体可能在同一文本中，也可能是其他文件，或是地理位置相距遥远的某台计算机上的文件。
  </div>
  <script>
    // scroll
    var box = document.getElementById('box');
    // 当拖动box中的滚动条的时候触发
    box.onscroll = function () {
      console.log(box.scrollLeft);
      console.log(box.scrollTop);

    }


    // // box滚动出去的距离
    // console.log(box.scrollLeft);
    // console.log(box.scrollTop);

    // // 内容的大小，包括padding 和未显示的内容，不包括滚动条
    // console.log(box.scrollWidth);
    // console.log(box.scrollHeight);

    // // 元素的大小 + padding   不包括滚动条
    // console.log(box.clientWidth);
    // console.log(box.clientHeight);
  </script>
</body>

</html>
```

## 4.4、案例

- **div匀速移动**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
    }
    #box {
      position: relative;
      background-color: red;
      width: 100px;
      height: 100px;
    }
  </style>
</head>
<body>
  <input type="button" value="开始" id="btn">
  <div id="box"></div>
  <script>
    var btn = document.getElementById('btn');
    var box = document.getElementById('box');
    btn.onclick = function () {
      var step = 6; 
      var target = 500;
      var timerId = setInterval(function () {
        if (box.offsetLeft >= target) {  
          clearInterval(timerId);
          box.style.left = target + 'px';
          return;
        }
        box.style.left = box.offsetLeft + step + 'px';
      }, 30);
    }
  </script>
</body>
</html>
```

- **获取鼠标在div内的坐标**

![](D:/Courseware/2020%E5%B9%B4%E8%AF%BE%E4%BB%B6/%E6%96%B0%E5%BC%80%E6%99%AE_%E5%89%8D%E7%AB%AF%E8%AF%BE%E7%A8%8B/03_JavaScript%E5%85%A5%E9%97%A8%E5%88%B0%E7%B2%BE%E9%80%9A/images04_dom/%E5%BE%AE%E4%BF%A1%E6%88%AA%E5%9B%BE_20200715221017.png)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Document</title>
  <style>
    body {
      margin: 0;
    }

    #box {
      width: 300px;
      height: 300px;
      border: 1px solid red;
      margin: 100px 10px 10px 100px;
    }
  </style>
</head>
<body>
  <div id="box">
    
  </div>
  <script src="common.js"></script>
  <script>
    var box = document.getElementById('box');
    box.onclick = function (e) {
      // 获取盒子在页面上的位置
      // console.log(this.offsetLeft);
      // console.log(this.offsetTop);

      e = e || window.event;
      // 获取鼠标在盒子中的位置 = 鼠标的坐标 - 盒子的坐标
      // var x = e.pageX
      var x = getPage(e).pageX - this.offsetLeft;
      var y = getPage(e).pageY - this.offsetTop;
      console.log(x);
      console.log(y);

    }
  </script>
</body>
</html>
```

- **拖拽案例**

```html
<!DOCTYPE html>
<html>

<head lang="en">
  <meta charset="UTF-8">
  <title></title>
  <style>
    * {
      margin: 0;
      padding: 0;
    }

    .nav {
      height: 30px;
      background: #87cefa;
      line-height: 30px;
      padding-left: 30px;
    }

    .nav a {
      color: #fff;
      text-align: center;
      font-size: 14px;
      text-decoration: none;

    }

    .d-box {
      width: 400px;
      height: 300px;
      border: 5px solid #eee;
      box-shadow: 2px 2px 2px 2px #666;
      position: absolute;
      top: 50%;
      left: 50%;
      background-color: white;
      /* 不让文字被选中 */
      user-select: none;
      transform: translate(-50%, -50%);
    }

    .hd {
      width: 100%;
      height: 35px;
      background-color: #87cefa;
      border-bottom: 1px solid #369;
      line-height: 35px;
      color: white;
      cursor: move;
    }

    #box_close {
      float: right;
      cursor: pointer;
    }
  </style>
</head>

<body>
  <div class="nav">
    <a href="javascript:;" id="register">注册信息</a>
  </div>
  <div class="d-box" id="d_box">
    <div class="hd" id="drop">注册信息 (可以拖拽)
      <span id="box_close">【关闭】</span>
    </div>
    <div class="bd"></div>
  </div>

  <script>
    // 获取盒子
    var box = document.getElementById('d_box');
    // 获取盒子标题区块
    var drop = document.getElementById('drop');

    drop.onmousedown = function (e) {
      // 兼容性处理
      var e = e || window.event;

      // 当鼠标在盒子标题区域按下的时候,获取鼠标在盒子里面的下标
      // 鼠标在盒子的下标 = 鼠标在页面的的下标 - 盒子的偏移量;
      var x = e.pageX - box.offsetLeft;
      var y = e.pageY - box.offsetTop;

      console.log(x + " " + y);

      document.onmousemove = function (e) {
        // 兼容性处理
        var e = e || window.event;
        // 当鼠标在页面上移动的时候。求盒子的坐标
        // 盒子的坐标 = 鼠标当前在页面中的位置 - 鼠标在盒子中的位置
        var boxX = e.pageX - x;
        var boxY = e.pageY - y;
        box.style.left = boxX + "px";
        box.style.top = boxY + "px";

      }
    }

    // 当鼠标在页面文档中弹起,移除移动跟随
    document.onmouseup = function () {
      document.onmousemove = null;
    }

    // 点击关闭按钮，隐藏盒子
    var box_close = document.getElementById('box_close');
    box_close.onclick = function () {
      box.style.display = 'none';
    }
  </script>
</body>

</html>
```

- **弹出登录窗口**

```html
<!DOCTYPE html>
<html>

<head lang="en">
  <meta charset="UTF-8">
  <title></title>
  <style>
    .login-header {
      width: 100%;
      text-align: center;
      height: 30px;
      font-size: 24px;
      line-height: 30px;
    }

    ul,li,ol,dl,dt,dd,div,p,span,h1,h2,h3,h4,h5,h6,a {
      padding: 0px;
      margin: 0px;
    }

    .login {
      width: 512px;
      height: 280px;
      position: absolute;
      border: #ebebeb solid 1px;
      left: 50%;
      top: 50%;
      background: #ffffff;
      box-shadow: 0px 0px 20px #ddd;
      z-index: 9999;
      display: none;
      transform: translate(-50%, -50%);
    }

    .login-title {
      width: 100%;
      margin: 10px 0px 0px 0px;
      text-align: center;
      line-height: 40px;
      height: 40px;
      font-size: 18px;
      position: relative;
      cursor: move;
      -moz-user-select: none;
      /*火狐*/
      -webkit-user-select: none;
      /*webkit浏览器*/
      -ms-user-select: none;
      /*IE10*/
      -khtml-user-select: none;
      /*早期浏览器*/
      user-select: none;
    }

    .login-input-content {
      margin-top: 20px;
    }

    .login-button {
      width: 50%;
      margin: 30px auto 0px auto;
      line-height: 40px;
      font-size: 14px;
      border: #ebebeb 1px solid;
      text-align: center;
    }

    .login-bg {
      width: 100%;
      height: 100%;
      position: fixed;
      top: 0px;
      left: 0px;
      background: #000000;
      filter: alpha(opacity=30);
      -moz-opacity: 0.3;
      -khtml-opacity: 0.3;
      opacity: 0.3;
      display: none;
    }

    a {
      text-decoration: none;
      color: #000000;
    }

    .login-button a {
      display: block;
    }

    .login-input input.list-input {
      float: left;
      line-height: 35px;
      height: 35px;
      width: 350px;
      border: #ebebeb 1px solid;
      text-indent: 5px;
    }

    .login-input {
      overflow: hidden;
      margin: 0px 0px 20px 0px;
    }

    .login-input label {
      float: left;
      width: 90px;
      padding-right: 10px;
      text-align: right;
      line-height: 35px;
      height: 35px;
      font-size: 14px;
    }

    .login-title span {
      position: absolute;
      font-size: 12px;
      right: -20px;
      top: -30px;
      background: #ffffff;
      border: #ebebeb solid 1px;
      width: 40px;
      height: 40px;
      border-radius: 20px;
    }
  </style>
</head>

<body>
  <div class="login-header"><a id="link" href="javascript:void(0);">点击，弹出登录框</a></div>
  <div id="login" class="login">
    <div id="title" class="login-title">登录会员
      <span><a id="closeBtn" href="javascript:void(0);" class="close-login">关闭</a></span>
    </div>
    <div class="login-input-content">
      <div class="login-input">
        <label>用户名：</label>
        <input type="text" placeholder="请输入用户名" name="info[username]" id="username" class="list-input">
      </div>
      <div class="login-input">
        <label>登录密码：</label>
        <input type="password" placeholder="请输入登录密码" name="info[password]" id="password" class="list-input">
      </div>
    </div>
    <div id="loginBtn" class="login-button"><a href="javascript:void(0);" id="login-button-submit">登录会员</a></div>
  </div>
  <!-- 遮盖层 -->
  <div id="bg" class="login-bg"></div>
  <script>
    // 显示登录框和遮盖层
    var login = document.getElementById('login');
    var bg = document.getElementById('bg');
    //1 点击按钮，弹出登录框和遮盖层
    var link = document.getElementById('link');
    link.onclick = function () {
      login.style.display = 'block';
      bg.style.display = 'block';
      return false;
    }

    // 2 点击关闭按钮，隐藏 登录框和遮盖层
    var closeBtn = document.getElementById('closeBtn');
    closeBtn.onclick = function () {
      // 隐藏 登录框和遮盖层
      login.style.display = 'none';
      bg.style.display = 'none';
    }

    // 3 拖拽
    var title = document.getElementById('title');
    title.onmousedown = function (e) {
      // 鼠标按下，求鼠标在盒子中的位置
      var x = e.pageX - login.offsetLeft;
      var y = e.pageY - login.offsetTop;

      document.onmousemove = function (e) {
        // 鼠标移动的时候， 盒子的坐标
        var loginX = e.pageX - x;
        var loginY = e.pageY - y;

        login.style.left = loginX + 'px';
        login.style.top = loginY + 'px';
      }
    }

    document.onmouseup = function () {
      // 移除鼠标移动的事件
      document.onmousemove = null;
    }
  </script>
</body>

</html>
```

- **放大镜案例**

  1、鼠标经过box的时候 显示 mask和bigBox ， 当鼠标离开box的时候隐藏mask和bigBox

  2、当鼠标在盒子中移动的时候，让mask和鼠标一起移动

  3、当mask移动的时候，让大图片移动

  ​	mask移动的距离 / mask最大能够移动的距离  = 大图片移动的距离 / 大图片最大能够移动的距离

```html
<!DOCTYPE html>
<html>

<head lang="en">
  <meta charset="UTF-8">
  <title></title>
  <style>
    * {
      margin: 0;
      padding: 0;
    }

    .box {
      width: 350px;
      height: 350px;
      margin: 100px;
      border: 1px solid #ccc;
      position: relative;
    }

    .big {
      width: 400px;
      height: 400px;
      position: absolute;
      top: 0;
      left: 360px;
      border: 1px solid #ccc;
      overflow: hidden;
      display: none;
    }

    .big img {
      position: absolute;
    }

    .mask {
      width: 175px;
      height: 175px;
      background: rgba(255, 255, 0, 0.4);
      position: absolute;
      top: 0px;
      left: 0px;
      cursor: move;
      display: none;
    }

    .small {
      position: relative;
    }
  </style>
</head>

<body>
  <div class="box" id="box">
    <div class="small">
      <img src="images/small.jpg" width="350" alt="" />
      <div class="mask"></div>
    </div>
    <div class="big">
      <img src="images/big.jpg" width="800" alt="" />
    </div>
  </div>
  <script>
    // 获取box、small盒子、big盒子
    var box = document.getElementById("box");
    var smallBox = box.children[0];
    var bigBox = box.children[1];

    // 获取小图片
    var smallImg = smallBox.children[0];
    // 获取遮罩
    var mask = smallBox.children[1];
    // 获取大图片
    var bigImg = bigBox.children[0];

    // 1、 鼠标经过box的时候 显示 mask和bigBox， 当鼠标离开box的时候隐藏mask和bigBox
    box.onmouseover = function () {
      mask.style.display = "block";
      bigBox.style.display = "block";
    }

    box.onmouseout = function () {
      mask.style.display = "none";
      bigBox.style.display = "none";
    }

    // 2、 当鼠标在盒子中移动的时候， 让mask和鼠标一起移动
    box.onmousemove = function (e) {
      // 获取鼠标在盒子里面的坐标,也就是mask的坐标
      var maskX = e.pageX - box.offsetLeft;
      var maskY = e.pageY - box.offsetTop;

      // 让鼠标位于盒子中间
      maskX = maskX - mask.offsetWidth / 2;
      maskY = maskY - mask.offsetHeight / 2;

      // 限制mask的活动范围
      maskX = maskX < 0 ? 0 : maskX;
      maskY = maskY < 0 ? 0 : maskY;

      maskX = maskX > box.offsetWidth - mask.offsetWidth ? box.offsetWidth - mask.offsetWidth : maskX;
      maskY = maskY > box.offsetHeight - mask.offsetHeight ? box.offsetHeight - mask.offsetHeight : maskY;

      // 把坐标设置给mask
      mask.style.left = maskX + "px";
      mask.style.top = maskY + "px";

      // 3、 当mask移动的时候， 让大图片移动
      //  mask移动的距离 / mask最大能够移动的距离 = 大图片移动的距离 / 大图片最大能够移动的距离
      // mask最大能够移动距离
      var maskMax = box.offsetWidth - mask.offsetWidth;
      var bingImgMax = bigImg.offsetWidth - bigBox.offsetWidth;

      // 计算得出大图片移动距离
      var bigImgX = maskX * bingImgMax / maskMax;
      var bigImgY = maskY * bingImgMax / maskMax;

      bigImg.style.left = -bigImgX + "px";
      bigImg.style.top = -bigImgY + "px";

    }
  </script>
</body>

</html>
```

- 回到顶部  

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        body {
            margin: 0;
        }

        header {
            width: 1024px;
            height: 150px;
            background: red;
            margin: auto;
        }

        section {
            width: 1024px;
            height: 550px;
            background: yellow;
            margin: 15px auto;

        }

        footer {
            width: 1024px;
            height: 150px;
            background: red;
            margin: auto;
        }

        aside {
            position: fixed;
            right: 0;
            bottom: 100px;
        }
    </style>
</head>

<body>
    <header></header>
    <section></section>
    <section></section>
    <section></section>
    <footer></footer>
    <aside>
        <a href="javascript:void(0)" id="goTop">回到顶部</a>
    </aside>

    <script src="comm.js"></script>
    <script>
        // 无论多远,300ms都要回到顶部
        var goTop = document.getElementById("goTop");

        goTop.onclick = function () {
            // 获取页面滚动出去的距离
            var y = getScroll().scrollTop;

            // 分30次滚动完毕,每次滚动多少距离
            var step = y / 10;

            var interId = setInterval(function () {
                if (getScroll().scrollTop <= 0) {
                    clearInterval(interId);
                    return;
                }
                // x 和 y 每次滚动的距离
                scrollBy(0, -step);
            }, 10)
        }
    </script>
</body>

</html>
```


<a id="p5-5"></a>
# 五、动画效果

## 5.1、动态时间显示

![1573389094458](images04_dom/1573389094458.png)

**需求:**

1. 当页面打开的时候,显示系统时间,并且每1s发生一次变化;
2. 月日时分秒必须确保是2位数

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        #timeDiv {
            font-size: 12px;

        }
    </style>
</head>

<body>
    <div id="timeDiv">

    </div>

    <script>
        var timeDiv = document.getElementById("timeDiv");

        setInterval(getTime, 1000)
        getTime();

        function getTime() {
            // 内置对象Date相关API
            var time = new Date();
            // 获取年月日
            var year = time.getFullYear();
            var month = time.getMonth() + 1;
            var date = time.getDate();
            // 获取时分秒
            var hour = time.getHours();
            var minutes = time.getMinutes();
            var seconds = time.getSeconds();

            var apm = hour >= 12 ? "下午" : "上午";

            var timeStr = "今天是 : " + year + "年" + toDoubleDigit(month) + "月" + toDoubleDigit(date) +
                "日,现在时间是 : " + apm + " " + toDoubleDigit(hour) + ":" + toDoubleDigit(minutes) + ":" +
                toDoubleDigit(seconds);

            timeDiv.innerHTML = timeStr;
        }

        function toDoubleDigit(num) {
            return num < 10 ? "0" + num : num;
        }
    </script>
</body>

</html>
```

## 5.2、随页面滚动的广告/侧边栏

![1573389232791](images04_dom/1573389232791.png)

[效果1]: https://www.amazon.cn/?tag=baidhydrcn-23&amp;ref=GS_sw_baidu_pc_YMX196_0180"固定广告"

**亚马逊广告效果:**

1. 固定在页面底部,而且居中
2. 点击右上角的X,可以关闭这个广告

![1573389371924](images04_dom/1573389371924.png)

document.documentElement.scrollTop	获取内容距离顶部的距离;

[效果2]: https://www.jd.com/?cu=true&amp;utm_source=baidu-pinzhuan&amp;utm_medium=cpc&amp;utm_campaign=t_288551095_baidupinzhuan&amp;utm_term=0f3d30c8dba7459bb52f2eb5eba8ac7d_0_df92db44522c4775b8483c75ec7529bb"京东导航"

**京东侧边栏回到顶部:**

1.固定在右侧的一个小导航

2.当我们点击回到顶部的时候,可以过渡回滚到顶部(不能使用锚点,因为锚点是瞬间回到顶部)

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        body {
            margin: 0;
            height: 1600px;
        }

        #amazonGg {
            width: 700px;
            height: 100px;
            background: yellow;
            position: fixed;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
        }

        #amazonGg>span {
            background: #ccc;
            padding: 3px 8px;
            display: inline-block;
            user-select: none;
            cursor: pointer;
            position: absolute;
            right: 0;
            top: 0;
        }
    </style>
</head>

<body>
    <div id="amazonGg">
        <span>&times;</span>
    </div>

    <script>
        var amazonGg = document.querySelector("#amazonGg");
        var closeBtn = document.querySelector("#amazonGg > span");
        closeBtn.onclick = function () {
            amazonGg.style.display = "none";
        }
    </script>
</body>

</html>
```

## 5.3、手风琴菜单

![1573389474346](images04_dom/1573389474346.png)

需求如下:
1、每张图片都有一个与之对应的内容块,但是这些内容块都是隐藏的

2、当我们点击哪张图片,那么对应的内容块显示,但是其他的内容块隐藏

3、如果点击图片,它是隐藏的,则显示;如果是显示的则隐藏;

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
    <style>
        * {
            margin: 0;
            padding: 0;
        }

        body {
            margin-top: 10px;
            margin-left: 100px;
        }

        #bigDiv {
            width: 183px;
            height: 550px;
            overflow: hidden;
            background: url("images/customer.jpg");
        }

        #imgDiv {
            margin: 210px auto 0;
            text-align: center;
            font-size: 14px;
            user-select: none;
            cursor: pointer;
            color: orangered;
            font-weight: bold;
        }

        #imgDiv>img {
            margin-top: -3px;
            cursor: pointer;
        }

        #imgDiv p {
            line-height: 26px;
        }

        #imgDiv>div {
            display: none;
        }
    </style>
</head>

<body>
    <div id="bigDiv">
        <div id="imgDiv">
            <img src="images/reg.jpg" alt="">
            <div>
                <p>点击注册</p>
                <p>认证中心</p>
            </div>
            <img src="images/buy.jpg" alt="">
            <div>
                <p>咨询</p>
                <p>投诉</p>
                <p>举报</p>
                <p>退款</p>
            </div>
            <img src="images/sale.jpg" alt="">
            <div>
                <p>安全中心</p>
                <p>物流中心</p>
                <p>资金流动</p>
                <p>纠纷处理</p>
            </div>
            <img src="images/person.jpg" alt="">
            <div>
                <p>修改资料</p>
                <p>账号申诉</p>
            </div>
        </div>
    </div>

    <script src="comm.js"></script>
    <script>
        var imgDiv = document.getElementById("imgDiv");

        var divs = imgDiv.getElementsByTagName("div");
        imgDiv.onclick = function (e) {
            e = e || window.event;
            var target = e.target || e.srcElement;
            if (target.nodeName.toLowerCase() === "img") {
                var imgTargetNext = getNextElementSibling(target);

                if (imgTargetNext.style.display === "block") {
                    imgTargetNext.style.display = "none"
                } else {
                    // 关闭所有div
                    for (var i = 0; i < divs.length; i++) {
                        divs[i].style.display = "none";
                    }

                    imgTargetNext.style.display = "block";
                }


            }
        }
    </script>
</body>

</html>
```

## 5.4、无缝滚动

需求：
1、四张图片的循环滚动(第一张图片上去、那么还是四张图片，第一张应该在最后面....)

2、鼠标移入暂停，移出继续

![1573389514671](images04_dom/1573389514671.png)

```html
<!doctype html>
<html>

<head>
    <title>页面标题</title>
    <meta charset="utf-8">
    <style>
        body,
        div,
        p,
        img {
            padding: 0;
            margin: 0;
        }

        .wrapDiv {
            /* 高度一定是计算出来的,一定要精确 */
            height: 277px;
            width: 230px;
            border: 1px solid #ccc;
            margin: 50px;
            border-radius: 5px 5px 0 0;
            position: relative;
            overflow: hidden;
        }

        .titleDiv {
            height: 35px;
            background: linear-gradient(#FBD596 5px, #F6BE81 12px, #F5B607 14px, #F6B908 16px, #F98A07 18px, #F58020);
            color: white;
            line-height: 35px;
            font-weight: bold;
            padding-left: 15px;
            font-size: 14px;
            user-select: none;
            position: relative;
            z-index: 3;
        }

        .cententDiv {
            height: 242px;
            font-size: 12px;
            position: absolute;
            /* 想让cententDiv动起来,把top的值变小即可 */
            top: 35px;
            z-index: 2;
        }

        .cententDiv img {
            /* 只给图片设置左右外边距 */
            margin: 0 10px;
            border: 1px solid #eee;
            vertical-align: middle;
        }

        .cententDiv>p {
            margin: 10px 0;
        }
    </style>
</head>

<body>
    <!-- 
            无缝滚动这个动态效果,需要对布局有非常精准的要求
            首先: 整个wrapDiv的大小要精确计算得出: 标题高度 (35px)+ 内容高度 (四张图片的高度(184)+8px+50px)
        -->
    <!-- wrapDiv是最外层的大div -->
    <div class="wrapDiv">
        <!-- 标题div -->
        <div class="titleDiv">
            新品上架
        </div>

        <!-- 滚动内容块 -->
        <div class="cententDiv" id="cententDiv">
            <p><img src="image/show1.jpg" alt=""> 打牌狂降价,三折直送</p>
            <p><img src="image/show2.jpg" alt=""> 大学要求老师开网店</p>
            <p><img src="image/show3.jpg" alt=""> 黑眼圈推荐,美白不停</p>
            <p><img src="image/show4.jpg" alt=""> 瘦身狂潮,修行之选</p>
            <p><img src="image/show1.jpg" alt=""> 打牌狂降价,三折直送</p>
            <p><img src="image/show2.jpg" alt=""> 大学要求老师开网店</p>
            <p><img src="image/show3.jpg" alt=""> 黑眼圈推荐,美白不停</p>
            <p><img src="image/show4.jpg" alt=""> 瘦身狂潮,修行之选</p>
        </div>
    </div>

    <script>
        var cententDiv = document.getElementById("cententDiv");
        var topVal = 35;
        var interId;
        // 使用定时器每隔多长时间改变cententDiv的top值
        interId = setInterval(slideFun, 20)

        cententDiv.onmouseover = function () {
            clearInterval(interId);
        }

        cententDiv.onmouseout = function () {
            interId = setInterval(slideFun, 20)
        }

        function slideFun() {
            if (topVal === -197) {
                topVal = 35;
            }
            topVal--;
            cententDiv.style.top = topVal + "px";
        }
    </script>
</body>

</html>
```

## 5.5、轮播图

![1573389606013](images04_dom/1573389606013.png)

常见轮播图分类:

1. 普通轮播图(无过渡效果)
2. 滑动轮播图
3. 淡入淡出轮播图

```html
<!doctype html>
<html>

<head>
    <title>页面标题</title>
    <meta charset="utf-8">
    <style>
        body,
        div,
        ul,
        li,
        img {
            margin: 0;
            padding: 0;
        }

        .slideDiv {
            position: relative;
        }

        .slideDiv img {
            width: 100%;
        }

        .slideDiv>ul {
            list-style: none;
            position: absolute;
            right: 20px;
            bottom: 40px;

        }

        .slideDiv li {
            width: 15px;
            height: 15px;
            background: #CCCACA;
            border: 1px solid white;
            display: inline-block;
            margin: 0 2px;
            cursor: pointer;
        }

        /* 这个.liSelected选择器里面定义是li选中的效果,但是因为优先级问题,没有显示效果 */
        /* 方法1: !important */
        /* 方式2: 通过选择器加强优先级 */
        .slideDiv li.liSelected {
            background: #CC0000;
            border: 1px solid #FF0000;
        }

        .textDiv {
            width: 100%;
            height: 30px;
            background: rgba(0, 0, 0, 0.3);
            position: absolute;
            bottom: 3px;
            font-size: 12px;
            color: white;
            line-height: 30px;
            padding-left: 20%;
            box-sizing: border-box;
        }
    </style>
</head>

<body>
    <!-- 
            普通轮播图,没有任何过渡效果的轮播图
            实现原理:
                每隔一段时间之后,改变图片的路径
         -->
    <div class="slideDiv" id="slideDiv">
        <a href=""><img src="image/product01.jpg" alt="" id="slideImg"></a>
        <ul>
            <li class="liSelected"></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
            <li></li>
        </ul>
        <div class="textDiv">
            新开普新闻：新开普获蚂蚁金服战略投资，携手打造校园新生态 2019-01-07
        </div>
    </div>

    <script>
        /*
            任意效果的轮播图,一般都是分两部分完成
                自动轮播
                手动轮播
        */
        // 获取得到图片元素节点
        var slideImg = document.getElementById("slideImg");

        // 用来控制图片值的变化,最小值是1,最大是6;如果到6就变为1
        var imgNum = 1;

        // 获取得到所有的li
        var lis = document.querySelectorAll("#slideDiv li");
        var ulEle = document.querySelector("#slideDiv ul");

        // 获取得到slideDiv
        var slideDiv = document.getElementById("slideDiv");

        var interId;

        // 自动轮播: 每隔指定时间,更换一张图片;每换一张图片,让对应的li处于选中状态(给对应的li添加liSelected类)
        interId = setInterval(sliderFun, 3000)

        function sliderFun() {
            if (imgNum === 6) {
                imgNum = 1;
            } else {
                imgNum++;
            }

            // 修改图片路径
            slideImg.src = "image/product0" + imgNum + ".jpg";

            // 修改对应li的选中效果
            changeLiStyle(imgNum - 1);
        }


        // 根据下标改变li的选中,参数是要选中li的下标
        function changeLiStyle(index) {
            for (var i = 0; i < lis.length; i++) {
                if (i === index) {
                    lis[i].className = "liSelected";
                } else {
                    lis[i].className = "";
                }
            }
        }


        // 手动轮播: 鼠标移入哪个li,则显示对应的图片; 鼠标移入整个slideDiv,那么停止轮播,移出继续轮播
        // 事件委托: 最好委托给直接父元素
        ulEle.onmouseover = function (e) {
            e = e || window.event;
            // 获取事件源
            var target = e.target || e.srcElement;

            // 如果事件源是li,则切换图片;如果是slideDiv,则停止轮播
            if (target.nodeName.toLowerCase() === "li") {
                var liIndex = getLiIndex(target);
                // 根据li的下标,改变li的选中效果
                changeLiStyle(liIndex);
                // 显示对应的图片
                slideImg.src = "image/product0" + (liIndex + 1) + ".jpg";

                imgNum = liIndex + 1;
            }
        }

        slideDiv.onmouseover = function () {
            clearInterval(interId);
        }

        slideDiv.onmouseout = function () {
            interId = setInterval(sliderFun, 3000)
        }

        // 获取li的下标,参数是li元素节点对象
        function getLiIndex(o) {
            var index = -1;
            for (var i = 0; i < lis.length; i++) {
                if (lis[i] === o) {
                    index = i;
                }
            }
            return index;
        }
    </script>
</body>

</html>
```

## 5.6、tab切换(tab标签页)

tab标签页: 在有限的区域显示更多的内容;

网易tab切换: 鼠标移入,切换到对应的内容;但是需要停留一定时间才能切换,避免了无脑切换问题;

![1573389657375](images04_dom/1573389657375.png)

[网易tab]: https://www.163.com/"网易tab"

![1573389846131](images04_dom/1573389846131.png)

[新浪tab]: https://www.sina.com.cn/"新浪tab"

```html
<!doctype html>
<html>

<head>
    <title>页面标题</title>
    <meta charset="utf-8">
    <style>
        body,
        ul,
        li,
        img,
        div {
            padding: 0;
            margin: 0;
        }

        /* 里面的图片是360*230 */
        .tabDiv {
            width: 360px;
            height: 260px;
            /* border: 1px solid black; */
            margin: 30px;
        }

        .tabDiv>ul {
            list-style: none;
            height: 30px;
            background: #F8F8F8;
            font-size: 14px;
            line-height: 30px;
            user-select: none;
            /* box-sizing: border-box; */
        }

        .tabDiv li {
            display: inline-block;
            padding: 0 15px;
            cursor: pointer;
            /* box-sizing: border-box; */
        }

        /* .tabDiv li:hover{
                background: white;
                border-top: 3px solid orangered;
            } */
        .tabDiv li.selected {
            background: white;
            border-top: 3px solid orangered;
            color: orangered;
        }

        .contentDiv div {
            display: none;
        }

        .contentDiv div.show {
            display: block;
        }
    </style>
</head>

<body>
    <div class="tabDiv" id="tabDiv">
        <!-- 我们使用ul和li来表示可以切换的tab标签 -->
        <ul>
            <li class="selected">图片</li>
            <li>专栏</li>
            <li>热点</li>
        </ul>

        <!-- 我们定义一个 contentDiv,这个contentDIv相当于用来实现对应内容的窗口-->
        <!-- 在contendDiv里面定义三个子div,然后给其添加内容 -->
        <div class="contentDiv" id="contentDiv">
            <div class="show"><img src="image/tupian.png" alt=""></div>
            <div><img src="image/zhuanlan.png" alt=""></div>
            <div><img src="image/redian.png" alt=""></div>
        </div>
    </div>
    <script src="comm.js"></script>
    <script>
        // 鼠标移入哪个li,则让li处于选中状态,其他li恢复默认
        var ulEle = document.querySelector("#tabDiv>ul");

        // 获取得到所有li的集合
        var lis = document.querySelectorAll("#tabDiv li");

        // 获取得到contentDiv里面的所有div元素集合
        var divs = document.querySelectorAll("#contentDiv > div");

        var outId;

        ulEle.onmouseover = function (e) {
            e = e || window.event;
            // 获取得到事件源
            var target = e.target || e.srcElement;

            if (target.nodeName.toLowerCase() === 'li') {
                // 获取到鼠标移入li,在ul里面的下标
                var liIndex = getElementIndex(lis, target);

                outId = setTimeout(function () {
                    // 给指定的li添加指定类,其他li取消该类效果
                    changeElementClass(lis, liIndex, "selected");

                    // 指定div显示,其他div隐藏,指定div添加.show,其他div取消类
                    changeElementClass(divs, liIndex, "show");
                }, 300)
            }
        }

        ulEle.onmouseout = function (e) {
            e = e || window.event;
            // 获取得到事件源
            var target = e.target || e.srcElement;

            if (target.nodeName.toLowerCase() === 'li') {
                clearTimeout(outId);
            }
        }
    </script>
</body>

</html>
```

## 5.7、表单的客户端检测

![1573389923367](images04_dom/1573389923367.png)

## 5.8、省市级联

需求:
1、如果没有选择第一个,那么就第二个下拉框就没有内容
2、如果选择了第一个,那么显示第一个对应的内容

![1573389948461](images04_dom/1573389948461.png)

```html
<!doctype html>
<html>

<head>
    <title>页面标题</title>
    <meta charset="utf-8">
    <style>
        select {
            width: 200px;
            height: 32px;
        }
    </style>
</head>

<body>
    所在地区:
    <select name="province" id="province">
        <option value="-1">请选择省份</option>
    </select>
    <select name="city" id="city">
        <option value="-1">请选择城市</option>
    </select>

    <script>
        //我们通过JS来定义一些假数据
        //无论是省份/直辖市/城市/地区,我们都使用假数据来存储

        //这个数组里面放：省份/直辖市
        var provinceArr = ["北京市", "河南省", "河北省", "上海市", "山东省"];

        //cityObj
        var cityObj = {
            "北京市": ["海淀区", "朝阳区", "昌平区", "丰台区"],
            "河南省": ["郑州市", "焦作市", "南阳市", "洛阳市", "许昌市", "信阳市", "安阳市", "濮阳市"],
            "河北省": ["石家庄市", "廊坊市", "邢台市", "雄安", "沙河市"],
            "上海市": ["黄浦区", "静安区", "徐汇区"],
            "山东省": ["青岛市", "日照市", "济南市", "烟台市"]
        }

        // 获取省份下拉框
        var province = document.getElementById("province");

        // 给省份select添加节点,provinceArr有几个数据,就在省份select添加几个节点
        for (var i = 0; i < provinceArr.length; i++) {
            // 创建option节点
            var opt = document.createElement("option");
            // 给option节点添加内容和value属性
            opt.value = provinceArr[i];
            opt.innerText = provinceArr[i];

            // 把节点添加到province下拉框
            province.appendChild(opt);
        }

        // 获取得到city元素节点
        var city = document.getElementById("city");

        // 当我们选择了指定的省份之后,在city下拉框里面加载对应的城市
        province.onchange = function () {
            // 每次改变,先清空city下拉列表的内容
            city.innerHTML = '<option value="-1">请选择城市</option>';

            // 获取选择的省份
            var selectProVal = this.value;
            console.log(selectProVal)
            if (selectProVal !== "-1") {
                // 根据省份获取得到省份对应的所有城市
                var cityArray = cityObj[selectProVal]; // 对象名["属性名"]

                for (var i = 0; i < cityArray.length; i++) {
                    // 创建option节点
                    var opt = document.createElement("option");
                    // 给option节点添加内容和value属性
                    opt.value = cityArray[i];
                    opt.innerText = cityArray[i];

                    city.appendChild(opt);
                }
            }
        }
    </script>
</body>

</html>
```

## 5.9、购物车操作

需求:
1、修改数量,下面的总价和节省金额发生变化
2、删除商品,提示是否删除,如果确定删除,那么才删除
3、删除之后更新总价和节省金额

![1573389969907](images04_dom/微信截图_20200720133929.png)

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <title>Title</title>
    <style>
        table,
        td {
            border: 1px solid black;
            border-collapse: collapse;
        }

        table {
            width: 980px;
            text-align: center;
            margin: 0 auto;
        }

        tr {
            height: 30px;
            line-height: 30px;
        }

        thead {
            font-weight: bold;

        }

        input[type=text] {
            width: 40px;
            height: 28px;
            text-align: center;
            border: 1px solid #A9A9A9;
        }

        tr td:nth-child(1) {
            width: 400px;
        }

        .showNull {
            display: none;
        }

        tbody>tr>td:nth-child(5) span {
            border: 1px solid #A9A9A9;
            height: 30px;
            display: inline-block;
            vertical-align: middle;
            width: 25px;
            user-select: none;
            cursor: pointer;
        }

        tbody>tr>td:nth-child(5) span:nth-child(1) {
            border-right: 0;
        }

        tbody>tr>td:nth-child(5) span:nth-child(3) {
            border-left: 0;
        }
    </style>
</head>

<body>
    <div id="showNull" class="showNull">
        购物车空空如也
    </div>
    <table id="shopCar">
        <caption>
            <h3>购物车</h3>
        </caption>
        <thead>
            <tr>
                <td>商品名</td>
                <td>原价</td>
                <td>优惠价</td>
                <td>打折</td>
                <td>数量</td>
                <td>删除</td>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>攀高搓背按摩器(蓝色) 定制版</td>
                <td>￥<span>258.00</span></td>
                <td>￥<span>129.00</span></td>
                <td>5.0折</td>
                <td><span>-</span><input type="text" value="1"><span>+</span></td>
                <td><a href="" class="deleteA">删除</a></td>
            </tr>
            <tr>
                <td>郝斌美国口语-美国口语成功训练系统(MP3)</td>
                <td>￥<span>480.00</span></td>
                <td>￥<span>292.90</span></td>
                <td>6.0折</td>
                <td><span>-</span><input type="text" value="2"><span>+</span></td>
                <td><a href="" class="deleteA">删除</a></td>
            </tr>
            <tr>
                <td>简 奥斯丁全集(DVD-9) (增BBC产品目录)</td>
                <td>￥<span>138.00</span></td>
                <td>￥<span>103.90</span></td>
                <td>8.0折</td>
                <td><span>-</span><input type="text" value="1"><span>+</span></td>
                <td><a href="" class="deleteA">删除</a></td>
            </tr>
        </tbody>
        <tfoot>
            <tr>
                <td>应付金额:</td>
                <td colspan="2"></td>

                <td>节省金额:</td>
                <td colspan="2"></td>

            </tr>
        </tfoot>
    </table>
    <script src="comm.js"></script>
    <script>
        // 获取得到表格元素节点
        var shopCar = document.getElementById("shopCar");

        // 获取得到tbody的所有行
        var tbodyEle = shopCar.tBodies[0];

        var tbodyRows = tbodyEle.rows;

        // 获取得到tfoot
        var tfootEle = shopCar.tFoot;

        var tfootRows = tfootEle.rows[0];

        var tfootCells = tfootRows.cells;
        // 计算应付金额
        // 计算节省金额
        // 应付金额 = 每件商品的优惠价 * 数量 的累加
        function getPay() {
            // 计算应付金额
            var paySum = 0;

            // 原本的金额
            var originalSum = 0;

            for (var i = 0; i < tbodyRows.length; i++) {
                // 获取得到tbody的每一行
                var row = tbodyRows[i];

                // 获取到当前行的所有单元格
                var rowCells = row.cells;

                // 获取得到原价
                var originalTd = rowCells[1];
                var originalSpan = originalTd.getElementsByTagName("span")[0];
                var originalPrice = parseFloat(originalSpan.innerText);

                // 获取得到优惠价
                var disTd = rowCells[2];
                var disSpan = disTd.getElementsByTagName("span")[0];
                var disPrice = parseFloat(disSpan.innerText);

                // 获取得到数量
                var countTd = rowCells[4];
                var countInput = countTd.getElementsByTagName("input")[0];
                var count = parseFloat(countInput.value);

                // 计算得到应付金额
                paySum += disPrice * count;

                // 计算得到原本金额
                originalSum += originalPrice * count;
            }

            tfootCells[1].innerText = "￥" + paySum.toFixed(2);
            tfootCells[3].innerText = "￥" + (originalSum - paySum).toFixed(2);
        }

        getPay();

        // 当修改输入框的值的时候,重新计算,对输入的值进行判断
        var inputs = shopCar.getElementsByTagName("input");

        for (var i = 0; i < inputs.length; i++) {
            var ip = inputs[i];

            // 添加获取焦点事件
            ip.onfocus = function () {
                var val = this.value;
                // 自定义属性
                this.setAttribute("val", val);
            }

            // 添加失去焦点事件
            ip.onblur = function () {
                // 判断值是否符合要求
                var v = Number(this.value);

                // 如果v是NaN,那么恢复之前的值
                if (isNaN(v)) {
                    this.value = this.getAttribute("val");
                } else {
                    getPay();
                }
            }

            // 给input之前的减号添加鼠标单击事件
            var previousSpan = getPreviousElementSibling(ip);
            previousSpan.onclick = function () {
                // 获取输入框的当前值
                var input = getNextElementSibling(this);
                if (input.value === "1") {
                    return;
                } else {
                    input.value--;

                }
                getPay();
            }

            // 给input之后的加号添加鼠标单击事件
            var nextSpan = getNextElementSibling(ip);
            nextSpan.onclick = function () {
                var input = getPreviousElementSibling(this);
                input.value++;
                getPay();
            }

        }


        var deleteAs = document.getElementsByClassName("deleteA");
        for (var i = 0; i < deleteAs.length; i++) {
            deleteAs[i].onclick = function () {
                var t = confirm("是否删除?")
                if (t) {
                    var deleteTr = this.parentNode.parentNode;
                    tbodyEle.removeChild(deleteTr);
                    getPay();
                }
                return false;
            }
        }
    </script>
</body>

</html>
```

## 5.10、模拟京东导航

![1573390008060](images04_dom/1573390008060.png)

```html
<!doctype html>
<html>

<head>
    <title>页面标题</title>
    <meta charset="utf-8">
    <style>
        body,
        div,
        ul,
        li,
        img {
            padding: 0;
            margin: 0;
        }

        body {
            background: #F4F4F4;
        }

        .navDiv {
            width: 190px;
            height: 470px;
            background: white;
            border: 1px solid black;
            padding: 10px 0;
            box-sizing: border-box;
            font-size: 14px;
            user-select: none;
            position: relative;
        }

        .navDiv>ul {
            list-style: none;
            padding: 0;
        }

        .navDiv li {
            cursor: pointer;
            /* padding: 4px; */
            padding: 4px 10px;
        }

        .navDiv li:hover {
            background: #F4F4F4;
        }

        /* 让li的div子元素,根据navDiv来定位 */
        .navDiv div {
            position: absolute;
            top: 0;
            left: 190px;
            display: none;
        }
    </style>
</head>

<body>
    <div class="navDiv" id="navDiv">
        <!-- 把li对应的内容都放在li里面即可 -->
        <ul>
            <li>家用电器
                <div><img src="image/jd1.png" alt=""></div>
            </li>
            <li>手机/运营商/数码
                <div><img src="image/jd2.png" alt=""></div>
            </li>
            <li>电脑/办公
                <div><img src="image/jd3.png" alt=""></div>
            </li>
            <li>家居/家具/家装/厨具
                <div><img src="image/jd4.png" alt=""></div>
            </li>
            <li>男装/女装/童装/内衣
                <div><img src="image/jd5.png" alt=""></div>
            </li>
            <li>美妆/个护清洁
                <div><img src="image/jd6.png" alt=""></div>
            </li>
        </ul>

    </div>

    <script>
        var navDiv = document.getElementById("navDiv");

        var allLis = navDiv.getElementsByTagName("li");

        for (var i = 0; i < allLis.length; i++) {
            allLis[i].onmouseover = function () {
                this.firstElementChild.style.display = "block";
            }
            allLis[i].onmouseout = function () {
                this.firstElementChild.style.display = "none";
            }
        }
    </script>
</body>

</html>
```


---

<a id="p6"></a>

# 第6篇 · JavaScript 高级

---

<a id="p6-1"></a>
# 一、浏览器深入解析

https://www.cnblogs.com/1rookie/p/7832930.html

https://segmentfault.com/a/1190000018428170

## 1.1、浏览器的组成 

​	浏览器在不断的演变中，并没有被要求呈现出一种特定的形态，但基本包括了如用户地址栏输入框、网络请求、浏览器文档解析、渲染引擎渲染网页、 JavaScript 引擎执行 js 脚本、客户端存储等功能。

​	从原理构成上分为七个模块，分别是User Interface（用户界面）、Browser engine（浏览器引擎）、Rendering engine（渲染引擎）、Networking（网络）、JavaScript Interpreter（js解释器）、UI Backend（UI后端）、Date Persistence（数据持久化存储）。

**结构如下所示：**

![](images05_higher/微信截图_20200720175655.png)

​	和大多数浏览器不同，Chrome 浏览器的每个标签页都分别对应一个渲染引擎实例。每个标签页都是一个独立的进程。

​	其中，最重要的是渲染引擎（内核）和JavaScript解释器（JavaScript引擎）。浏览器内核主要负责 HTML、CSS 的解析，页面布局、渲染与复合层合成，主流的内核有：Blink、Webkit、Gecko、EdgeHTML、Trident。

​	JavaScript引擎负责 JavaScript 代码的解释与执行，主流的 JavaScript 引擎有：V8、SpiderMonkey、JavaScriptCore、Chakra。

​	首先浏览器是一个软件，就和qq，wechat，没什么差别，只是功能不一样。qq，wechat是社交类，而浏览器就是专门用来访问和浏览万维网页面的客户端软件。

**1. User Interface(用户界面)：**

​	包括工具栏、地址栏、前进/后退按钮、书签菜单、可视化页面加载进度、智能下载处理、首选项、打印等。除了浏览器主窗口显示请求的页面之外，其他显示的部分都属于用户界面。

**2. Browser engine(浏览器引擎)：**

​	浏览器引擎是一个可嵌入的组件，其为渲染引擎提供高级接口。

​	浏览器引擎可以加载一个给定的URI，并支持诸如：前进/后退/重新加载等浏览操作。

​	浏览器引擎提供查看浏览会话的各个方面的挂钩，例如：当前页面加载进度。

​	浏览器引擎还允许查询/修改渲染引擎设置。

**3. Rendering Engine(渲染引擎)：**

​	渲染引擎为指定的URI生成可视化的表示。

​	渲染引擎能够显示HTML和XML文档，可选择CSS样式，以及嵌入式内容（如图片）。

​	渲染引擎能够准确计算页面布局，可使用“回流”算法逐步调整页面元素的位置。

​	渲染引擎内部包含HTML解析器。

​	Chrome为每个Tab分配了各自的渲染引擎实例，每个Tab就是一个独立的进程。

**4. Networking(网络)**

​	网络系统实现HTTP和FTP等文件传输协议。 

​	网络系统可以在不同的字符集之间进行转换，为文件解析MIME媒体类型。

​	网络系统可以实现最近检索资源的缓存功能。

**5. JavaScript Interpreter(JS解释器)**

​	JavaScript解释器能够解释并执行嵌入在网页中的JavaScript（又称ECMAScript）代码。 为了安全起见，浏览器引擎或渲染引擎可能会禁用某些JavaScript功能，如弹出窗口的打开。

**6. XML Parser(XML解析器)**

​	XML解析器可以将XML文档解析成文档对象模型（Document Object Model，DOM）树。 XML解析器是浏览器架构中复用最多的子系统之一，几乎所有的浏览器实现都利用现有的XML解析器，而不是从头开始创建自己的XML解析器

​	功能相似的HTML解析器和XML解析器为什么前者划分在渲染引擎中，后者作为独立的系统？

​	XML解析器对于系统来说，其功能并不是关键性的，但是从复用角度来说，XML解析器是一个通用的，可重用的组件，具有标准的，定义明确的接口。相比之下，HTML解析器通常与渲染引擎紧耦合。

**7. UI Backend(显示后端)**

​	用来绘制类似组合选择框及对话框等基本组件，具有不特定于某个平台的通用接口，底层使用操作系统的用户接口。

**8. Data Persistence(数据持久层)**

​	数据持久层将与浏览会话相关联的各种数据存储在硬盘上。 这些数据可能是诸如：书签、工具栏设置等这样的高级数据，也可能是诸如：Cookie，安全证书、缓存等这样的低级数据。

## 1.2、浏览器内核

​	浏览器内核负责对网页语法的解释（如标准通用标记语言下的一个应用HTML、JavaScript）并渲染（显示）网页。

​	浏览器的内核的不同对于网页的语法解释会有不同，所以渲染的效果也不相同。所有网页浏览器、电子邮件客户端以及其它需要编辑、显示网络内容的应用程序都需要内核。

​	内核分为两个部分：渲染引擎和js引擎，由于js引擎越来越独立，内核就倾向于只指渲染引擎。

​	不同的浏览器内核对网页编写语法的解释也有不同，因此同一网页在不同的内核的浏览器里的渲染（显示）效果也可能不同，这也是网页编写者需要在不同内核的浏览器中测试网页显示效果的原因。

**1. 渲染引擎**

​	负责请求网络页面资源加以解析排版并呈现给用户，渲染引擎可以显示html、xml文档及图片，它也可以借助插件显示其他类型数据，例如使用PDF阅读器插件，可以显示PDF格式。

**2. js引擎**

​	JS 引擎则是解析 Javascript 语言，执行 javascript 语言来实现网页的动态效果。

**3. 当前主流内核**

**Trident ([‘traɪd(ə)nt])：普遍称作 “IE内核”**

​	该内核程序在 1997 年的 IE4 中首次被采用，是微软在 Mosaic（”马赛克”，这是人类历史上第一个浏览器，从此网页可以在图形界面的窗口浏览） 代码的基础之上修改而来的，并沿用到 IE11，也被普遍称作 “IE内核”。

​	IE 从版本 11 开始，初步支持 WebGL 技术。IE8 的 JavaScript 引擎是 Jscript，IE9 开始用 Chakra，这两个版本区别很大，Chakra 无论是速度和标准化方面都很出色。

​	Window10 发布后，IE 将其内置浏览器命名为 Edge，Edge 最显著的特点就是新内核 EdgeHTML。

**Gecko ([‘gekəʊ])：Firefox 内核**

​	Gecko 内核的浏览器Firefox (火狐) 用户最多，所以有时也会被称为 Firefox 内核，此外 Gecko 也是一个跨平台内核，可以在Windows、 BSD、Linux 和 Mac OS X 中使用。

**Webkit：**

​	webkit内核 可以说是以硬件盈利为主的苹果公司给软件行业的最大贡献之一。随后，2008 年谷歌公司发布 chrome 浏览器，采用的 chromium 内核便 fork 了 Webkit。

**Chromium/Blink：**

​	2008 年，谷歌公司发布了 chrome 浏览器，浏览器使用的内核被命名为 chromium。

​	chromium fork 自开源引擎 webkit，却把 WebKit 的代码梳理得可读性提高很多，所以以前可能需要一天进行编译的代码，现在只要两个小时就能搞定。因此 Chromium 引擎和其它基于 WebKit 的引擎所渲染页面的效果也是有出入的。所以有些地方会把 chromium 引擎和 webkit 区分开来单独介绍，而有的文章把 chromium 归入 webkit 引擎中，都是有一定道理的。

​	谷歌公司还研发了自己的 Javascript 引擎，V8，极大地提高了 Javascript 的运算速度。

​	Blink 引擎问世后，国产各种 chrome 系的浏览器也纷纷投入 Blink 的怀抱。

​	Blink是一个由Google和Opera Software开发的浏览器排版引擎，Opera表示将会跟随谷歌采用其Blink浏览器核心，同时参与了Blink的开发。

**Presto ([‘prestəʊ])：opera 的 “前任” 内核**

​	为何说是 “前任”，因为最新的 opera 浏览器早已将之抛弃从而投入到了谷歌大本营。

## 1.3、JavaScript引擎

JavaScript引擎是一个专门处理JavaScript脚本的虚拟机，一般会附带在网页浏览器之中。

![](images05_higher/微信截图_20200720185644.png)

**Mozilla**

●　SpiderMonkey，第一款JavaScript引擎，由Brendan Eich在Netscape Communications时编写，用于Mozilla Firefox 1.0～3.0版本。

●　Rhino，由Mozilla基金会管理，开放源代码，完全以Java编写。

●　TraceMonkey，基于实时编译的引擎，其中部份代码取自Tamarin引擎，用于Mozilla Firefox 3.5～3.6版本。

●　JaegerMonkey，结合追踪和组合码技术大幅提高性能，部分技术借凿了V8、JavaScriptCore、WebKit，用于Mozilla Firefox 4.0以上版本。

**Google**

●　V8，开放源代码，由Google丹麦开发，是Chrome浏览器的一部分。

V8是被设计用来提高网页浏览器内部JavaScript执行的性能，那么如何提高性能呢？

​	为了提高性能，v8会把js代码转换为高效的机器码，而不在是依赖于解释器去执行。v8引入了JIT在运行时把js代码进行转换为机器码。这里的主要区别在于V8不生成字节码或任何中间代码。

V8介绍：https://www.jianshu.com/p/81f6ded64ab2

JIT:https://www.zhihu.com/question/19672491

**微软**

●　Chakra (JScript引擎)，中文译名为查克拉，用于Internet Explorer 9的32位版本。

**Opera**

●　Linear A，用于Opera 4.0～6.1版本。

●　Linear B，用于Opera 7.0～9.2版本。

●　Futhark，用于Opera 9.5～10.2版本。

●　Carakan，由Opera软件公司编写，自Opera10.50版本开始使用。

**其它**

●　KJS，KDE的ECMAScript/JavaScript引擎，最初由Harri Porten开发，用于KDE项目的Konqueror网页浏览器中。

●　Narcissus，开放源代码，由Brendan Eich编写（他也参与编写了第一个SpiderMonkey）。

●　Tamarin，由Adobe Labs编写，Flash Player 9所使用的引擎。

●　Nitro（原名SquirrelFish），为Safari 4编写。

## 1.4、浏览器的渲染过程

### 1.4.1、渲染过程

![](images05_higher/微信截图_20200720212537.png)

从上面这个图上，我们可以看到，浏览器渲染过程如下： 

1. 解析HTML，生成DOM树，解析CSS，生成CSSOM树
2. 将DOM树和CSSOM树结合，生成渲染树(Render Tree)
3. Layout(回流):根据生成的渲染树，进行回流(Layout)，得到节点的几何信息（位置，大小）
4. Painting(重绘):根据渲染树以及回流得到的几何信息，得到节点的绝对像素
5. Display:将像素发送给GPU，展示在页面上。

### 1.4.2、生成渲染树

渲染过程看起来很简单，让我们来具体了解下每一步具体做了什么。

![](images05_higher/微信截图_20200720212936.png)

- 为了构建渲染树，浏览器主要完成了以下工作：
  1. 从DOM树的根节点开始遍历每个可见节点。
  2. 对于每个可见的节点，找到CSSOM树中对应的规则，并应用它们。
  3. 根据每个可见节点以及其对应的样式，组合生成渲染树
- 什么是不可见节点
  1. 一些不会渲染输出的节点，比如script、meta、link等。
  2. 一些通过css进行隐藏的节点。比如display:none。注意，利用visibility和opacity隐藏的节点，还是会显示在渲染树上的（因为还占据文档空间）。只有display:none的节点才不会显示在渲染树上。
- 注意：渲染树只包含可见的节点

## 1.5、回流和重绘

### 1.5.1、回流

​	前面我们通过构造渲染树，我们将可见DOM节点以及它对应的样式结合起来，可是我们还需要计算它们在设备视口(viewport)内的确切位置和大小，这个计算的阶段就是回流。

​	为了弄清每个对象在网站上的确切大小和位置，浏览器从渲染树的根节点开始遍历，我们可以以下面这个实例来表示：

```html
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Critial Path: Hello world!</title>
  </head>
  <body>
    <div style="width: 50%">
      <div style="width: 50%">Hello world!</div>
    </div>
  </body>
</html>
```

​		我们可以看到，第一个div将节点的显示尺寸设置为视口宽度的50%，第二个div将其尺寸设置为父节点的50%。而在回流这个阶段，我们就需要根据视口具体的宽度，将其转为实际的像素值（如下图）

![](images05_higher/微信截图_20200720213421.png)

### 1.5.2、重绘

​	最终，我们通过构造渲染树和回流阶段，我们知道了哪些节点是可见的，以及可见节点的样式和具体的几何信息(位置、大小)，那么我们就可以将渲染树的每个节点都转换为**屏幕上的实际像素**，这个阶段就叫做重绘节点。

实际像素值和屏幕像素:

​	https://www.zhihu.com/question/21149600

### 1.5.3、何时发生回流重绘

​	既然知道了浏览器的渲染过程后，我们就来探讨下，何时会发生回流重绘。

​	我们前面知道了，回流这一阶段主要是计算节点的位置和几何信息，那么当页面布局和几何信息发生变化的时候，就需要回流。比如以下情况：

- 添加或删除可见的DOM元素
- 元素的位置发生变化
- 元素的尺寸发生变化（包括外边距、内边框、边框大小、高度和宽度等）
- 内容发生变化，比如文本变化或图片被另一个不同尺寸的图片所替代。
- 页面一开始渲染的时候（这肯定避免不了）
- 浏览器的窗口尺寸变化（因为回流是根据视口的大小来计算元素的位置和大小的）

注意：回流一定会触发重绘，而重绘不一定会回流.

​	根据改变的范围和程度，渲染树中或大或小的部分需要重新计算，有些改变会触发整个页面的重排，比如，滚动条出现的时候或者修改了根节点。

### 1.5.4、减少回流和重绘

#### 1.5.4.1、最小化重绘和重排

​	由于重绘和重排可能代价比较昂贵，因此最好就是可以减少它的发生次数。**为了减少发生次数，我们可以合并多次对DOM和样式的修改，然后一次处理掉**。

考虑这个例子:

```js
var el = document.getElementById('test');
el.style.padding = '5px';
el.style.borderLeft = '1px';
el.style.borderRight = '2px'
```

​	例子中，有三个样式属性被修改了，每一个都会影响元素的几何结构，引起回流。当然，大部分现代浏览器都对其做了优化，因此，只会触发一次重排。但是如果在旧版的浏览器或者在上面代码执行的时候，有其他代码访问了布局信息(上文中的会触发回流的布局信息)，那么就会导致三次重排。

​	因此，我们可以合并所有的改变然后依次处理，比如我们可以采取以下的方式：

- 使用cssText

  ```js
  var el = document.getElementById('test');
  el.style.cssText += 'border-left: 1px; border-right: 2px;   padding: 5px;
  ```

- 修改CSS的class

  ```js
  var el = document.getElementById('test');
  // 在使用 += 操作class的时候,一定要记得添加一个空格
  el.className += ' active';
  ```

#### 1.5.4.2、批量修改DOM

当我们需要对DOM对一系列修改的时候，可以通过以下步骤减少回流重绘次数：

1. 使元素脱离文档流,不是指的定位脱离文档流
2. 对其进行多次修改
3. 将元素带回到文档中。

该过程的第二步和第三步可能会引起回流，但是经过第一步之后，对DOM的所有修改都不会引起回流，因为它已经不在渲染树了。

有三种方式可以让DOM脱离文档流：

1. 隐藏元素，应用修改，重新显示
2. 使用文档片段(document fragment)在当前DOM之外构建一个子树，再把它拷贝回文档。
3. 将原始元素拷贝到一个脱离文档的节点中，修改节点后，再替换原始的元素。

考虑我们要执行一段批量插入节点的代码：

```js
function appendDataToElement(appendToElement, data) {
    var li;
    for (let i = 0; i < data.length; i++) {
        li = document.createElement('li');
        li.textContent = 'text';
        appendToElement.appendChild(li);
    }
}

var ul = document.getElementById('list');
appendDataToElement(ul, data);
```

如果我们直接这样执行的话，由于每次循环都会插入一个新的节点，会导致浏览器回流一次。

我们可以使用这三种方式进行优化:

**方式1: 隐藏元素，应用修改，重新显示**

这个会在展示和隐藏节点的时候，产生两次重绘

```js
function appendDataToElement(appendToElement, data) {
    var li;
    for (let i = 0; i < data.length; i++) {
        li = document.createElement('li');
        li.textContent = 'text';
        appendToElement.appendChild(li);
    }
}
var ul = document.getElementById('list');
ul.style.display = 'none';
appendDataToElement(ul, data);
ul.style.display = 'block';
```

**方式2：使用文档片段(document fragment)在当前DOM之外构建一个子树，再把它拷贝回文档**

createdocumentfragment()方法创建了一虚拟的节点对象，节点对象包含所有属性和方法。

```js
var ul = document.getElementById('list');

var fragment = document.createDocumentFragment();

appendDataToElement(fragment, data);

ul.appendChild(fragment);
```

**方式3：将原始元素拷贝到一个脱离文档的节点中，修改节点后，再替换原始的元素。**

```js
var ul = document.getElementById('list');

var clone = ul.cloneNode(true);

appendDataToElement(clone, data);

ul.parentNode.replaceChild(clone, ul);
```

#### 1.5.4.3、对于复杂动画效果,使用绝对定位让其脱离文档流

对于复杂动画效果，由于会经常的引起回流重绘，因此，我们可以使用绝对定位，让它脱离文档流。否则会引起父元素以及后续元素频繁的回流。

#### 1.5.4.4、css3硬件加速（GPU加速）

比起考虑如何减少回流重绘，我们更期望的是，根本不要回流重绘。这个时候，css3硬件加速就闪亮登场啦！！

划重点：使用css3硬件加速，可以让transform、opacity、filters这些动画不会引起回流重绘 。但是对于动画的其它属性，比如background-color这些，还是会引起回流重绘的，不过它还是可以提升这些动画的性能。

常见的触发硬件加速的css属性：

- transform
- opacity
- filters
- Will-change

如果你为太多元素使用css3硬件加速，会导致内存占用较大，会有性能问题。

```html
Will-change:
	https://developer.mozilla.org/zh-CN/docs/Web/CSS/will-change
	https://www.zhangxinxu.com/wordpress/2015/11/css3-will-change-improve-paint/
```

## 1.6、浏览器静态资源缓存机制

### 1.6.1、为什么需要缓存？

缓存可以说是性能优化中简单高效的一种优化方式了。一个优秀的缓存策略可以缩短网页请求资源的距离，减少延迟，并且由于缓存文件可以重复利用，还可以减少带宽，降低网络负荷。

对于一个数据请求来说，可以分为发起网络请求、后端处理、浏览器响应三个步骤。浏览器缓存可以帮助我们在第一和第三步骤中优化性能。比如说直接使用缓存而不发起请求（强缓存），或者发起了请求但后端存储的数据和前端一致，那么就没有必要再将数据回传回来，这样就减少了响应数据（协商缓存）。

### 1.6.2、缓存位置

从缓存位置上来说分为四种，并且各自有优先级，当依次查找缓存且都没有命中的时候，才会去请求网络。

> - Service Worker
> - Memory Cache
> - Disk Cache
> - Push Cache

**1.Service Worker**

​	Service Worker 是运行在浏览器背后的独立线程，一般可以用来实现缓存功能。使用 Service Worker的话，传输协议必须为 HTTPS。因为 Service Worker 中涉及到请求拦截，所以必须使用 HTTPS 协议来保障安全。Service Worker 的缓存与浏览器其他内建的缓存机制不同，它可以让我们自由控制缓存哪些文件、如何匹配缓存、如何读取缓存，并且缓存是持续性的。

​	Service Worker 实现缓存功能一般分为三个步骤：首先需要先注册 Service Worker，然后监听到 install 事件以后就可以缓存需要的文件，那么在下次用户访问的时候就可以通过拦截请求的方式查询是否存在缓存，存在缓存的话就可以直接读取缓存文件，否则就去请求数据。

​	当 Service Worker 没有命中缓存的时候，我们需要去调用 fetch 函数获取数据。也就是说，如果我们没有在 Service Worker 命中缓存的话，会根据缓存查找优先级去查找数据。但是不管我们是从 Memory Cache 中还是从网络请求中获取的数据，浏览器都会显示我们是从 Service Worker 中获取的内容。

**2.Memory Cache**

​	Memory Cache 也就是内存中的缓存，主要包含的是当前中页面中已经抓取到的资源,例如页面上已经下载的样式、脚本、图片等。读取内存中的数据肯定比磁盘快,内存缓存虽然读取高效，可是缓存持续性很短，会随着进程的释放而释放。 一旦我们关闭 Tab 页面，内存中的缓存也就被释放了。

​	那么既然内存缓存这么高效，我们是不是能让数据都存放在内存中呢？

​	这是不可能的。计算机中的内存一定比硬盘容量小得多，操作系统需要精打细算内存的使用，所以能让我们使用的内存必然不多。

​	当我们访问过页面以后，再次刷新页面，可以发现很多数据都来自于内存缓存

​	内存缓存中有一块重要的缓存资源是preloader相关指令（例如`<link rel="prefetch">`）下载的资源。总所周知preloader的相关指令已经是页面优化的常见手段之一，它可以一边解析js/css文件，一边网络请求下一个资源。

​	需要注意的事情是，内存缓存在缓存资源时并不关心返回资源的HTTP缓存头Cache-Control是什么值，同时资源的匹配也并非仅仅是对URL做匹配，还可能会对Content-Type，CORS等其他特征做校验。

**3.Disk Cache**

​	Disk Cache 也就是存储在硬盘中的缓存，读取速度慢点，但是什么都能存储到磁盘中，比之 Memory Cache 胜在容量和存储持久性上。

​	在所有浏览器缓存中，Disk Cache 覆盖面基本是最大的。它会根据 HTTP Header 中的字段判断哪些资源需要缓存，哪些资源可以不请求直接使用，哪些资源已经过期需要重新请求。并且即使在跨站点的情况下，相同地址的资源一旦被硬盘缓存下来，就不会再次去请求数据。绝大部分的缓存都来自 Disk Cache，关于 HTTP 的协议头中的缓存字段，我们会在下文进行详细介绍。

​	浏览器会把哪些文件丢进内存中？哪些丢进硬盘中？

​	关于这点，网上说法不一，不过以下观点比较靠得住：

​	对于大文件来说，大概率是不存储在内存中的，反之优先

​	当前系统内存使用率高的话，文件优先存储进硬盘

**4.Push Cache**

​	Push Cache（推送缓存）是 HTTP/2 中的内容，当以上三种缓存都没有命中时，它才会被使用。它只在会话（Session）中存在，一旦会话结束就被释放，并且缓存时间也很短暂，在Chrome浏览器中只有5分钟左右，同时它也并非严格执行HTTP头中的缓存指令。

​	Push Cache 在国内能够查到的资料很少，也是因为 HTTP/2 在国内不够普及。这里推荐阅读Jake Archibald的 HTTP/2 push is tougher than I thought 这篇文章，文章中的几个结论：

- 所有的资源都能被推送，并且能够被缓存,但是 Edge 和 Safari 浏览器支持相对比较差

- 可以推送 no-cache 和 no-store 的资源

- 一旦连接被关闭，Push Cache 就被释放

- 多个页面可以使用同一个HTTP/2的连接，也就可以使用同一个Push Cache。这主要还是依赖浏览器的实现而定，出于对性能的考虑，有的浏览器会对相同域名但不同的tab标签使用同一个HTTP连接。

- Push Cache 中的缓存只能被使用一次

- 浏览器可以拒绝接受已经存在的资源推送

- 你可以给其他域名推送资源

  如果以上四种缓存都没有命中的话，那么只能发起请求来获取资源了。

那么为了性能上的考虑，大部分的接口都应该选择好缓存策略，通常浏览器缓存策略分为两种：强缓存和协商缓存，并且缓存策略都是通过设置 HTTP Header 来实现的。

```html
More:
	https://blog.csdn.net/Fly_as_tadpole/article/details/86629288
```

<a id="p6-2"></a>
# 二、正则表达式

## 2.1、正则表达式简介

**什么是正则表达式**

​	正则表达式：用于匹配规律规则的表达式，正则表达式最初是科学家对人类神经系统的工作原理的早期研究，现在在编程语言中有广泛的应用。正则表通常被用来检索、替换那些符合某个模式(规则)的文本。

​	正则表达式(Regular Expression)是一种文本模式，包括普通字符（例如，a 到 z 之间的字母）和特殊字符（称为"元字符"）。

​	正则表达式使用单个字符串来描述、匹配一系列匹配某个句法规则的字符串。

​	正则表达式是繁琐的，但它是强大的，学会之后的应用会让你除了提高效率外，会给你带来绝对的成就感。

​	许多程序设计语言都支持利用正则表达式进行字符串操作。

**正则表达式的作用**

通过使用正则表达式，可以：

- 测试字符串内的模式（匹配）。
  例如，可以测试输入字符串，以查看字符串内是否出现电话号码模式或信用卡号码模式。这称为数据验证。
- 替换文本（替换）。
  可以使用正则表达式来识别文档中的特定文本，完全删除该文本或者用其他文本替换它。
- 基于模式匹配从字符串中提取子字符串（提取）。
  可以查找文档内或输入域内特定的文本

**正则表达式的特点**

​	灵活性、逻辑性和功能性非常的强

​	可以迅速地用极简单的方式达到字符串的复杂控制

​	对于刚接触的人来说，比较晦涩难懂	

**发展历史**

​	正则表达式的"祖先"可以一直上溯至对人类神经系统如何工作的早期研究。Warren McCulloch 和 Walter Pitts 这两位神经生理学家研究出一种数学方式来描述这些神经网络。

​	1956 年, 一位叫 Stephen Kleene 的数学家在 McCulloch 和 Pitts 早期工作的基础上，发表了一篇标题为"神经网事件的表示法"的论文，引入了正则表达式的概念。正则表达式就是用来描述他称为"正则集的代数"的表达式，因此采用"正则表达式"这个术语。

​	随后，发现可以将这一工作应用于使用 Ken Thompson 的计算搜索算法的一些早期研究，Ken Thompson 是 Unix 的主要发明人。正则表达式的第一个实用应用程序就是 Unix 中的 qed 编辑器。

​	如他们所说，剩下的就是众所周知的历史了。从那时起直至现在正则表达式都是基于文本的编辑器和搜索工具中的一个重要部分。

**应用领域**

​	目前，正则表达式已经在很多软件中得到广泛的应用，包括 *nix（Linux, Unix等）、HP 等操作系统，PHP、C#、Java 等开发环境，以及很多的应用软件中，都可以看到正则表达式的影子。

## 2.2、正则表达式的组成

- 普通字符abc  123
- 特殊字符(元字符)：正则表达式中有特殊意义的字符\d  \w

### 2.2.1、字符类：

| 字符类          | 说明                                                         |
| --------------- | ------------------------------------------------------------ |
| [abc]           | 只能是a b c中的任意一个,也就是说[]里面的内容只能选择任意一个 |
| [^abc]          | 任何字符，除了 a、b 或 c（否定）                             |
| [a-z]           | a 到 z 中的任意一个                                          |
| [^a-z]          | 非a 到 z 中的任意一个                                        |
| [a-zA-Z]        | a 到 z 或 A 到 Z，两头的字母包括在内（范围）                 |
| [0-9]           | 0-9之间的任意一个                                            |
| [\u4e00-\u9fa5] | 表示汉字的取值范围                                           |

### 2.2.2、元字符：

| 元字符 | 说明                           |
| ------ | ------------------------------ |
| \d     | 匹配数字                       |
| \D     | 匹配任意非数字的字符           |
| \w     | 匹配字母或数字或下划线         |
| \W     | 匹配任意不是字母，数字，下划线 |
| \s     | 匹配任意的空白符               |
| \S     | 匹配任意不是空白符的字符       |
| .      | 匹配除换行符以外的任意单个字符 |
| ^      | 表示匹配行首的文本(以谁开始)   |
| $      | 表示匹配行尾的文本(以谁结束)   |

### 2.2.3、限定符：

| 限定符 | 说明             |
| ------ | ---------------- |
| *      | 重复零次或更多次 |
| +      | 重复一次或更多次 |
| ?      | 重复零次或一次   |
| {n}    | 重复n次          |
| {n,}   | 重复n次或更多次  |
| {n,m}  | 重复n到m次       |

### 2.2.4、条件:

| 条件           | 说明         |
| -------------- | ------------ |
| (?![0-9]+$)    | 不能全是数字 |
| (?![a-zA-Z]+$) | 不能全是字母 |

### 2.2.5、其他

| 其他 | 说明                                                         |
| ---- | ------------------------------------------------------------ |
| []   | 字符串用中括号括起来，表示匹配其中的任一字符                 |
| [^]  | 匹配除中括号以内的内容                                       |
| \    | 转义符                                                       |
| \|   | 或者，选择两者中的一个。注意 \| 将左右两边分为两部分，而不管左右两边有多长多乱 |
| ()   | 从两个直接量中选择一个，分组                                 |

## 2.3、简单案例

验证手机号：

```javascript
^\d{11}$
```

验证邮编：

```javascript
^\d{6}$
```

验证日期 2012-5-01 

```javascript
^\d{4}-\d{1,2}-\d{1,2}$
```

验证邮箱 xxx@newcapec.com.cn：

```javascript
^\w+@\w+\.\w+$
```

验证IP地址 192.168.1.10

```javascript
^\d{1,3}(.\d{1,3}){3}$
```

## 2.4、使用正则表达式

### 2.4.1、创建正则对象

方式1：

```javascript
var reg = new RegExp('\d', 'i');
var reg = new RegExp('\d', 'gi');
```

方式2：

```javascript
var reg = /\d/i;
var reg = /\d/gi;
```

**参数**

| 标志 | 说明                |
| ---- | ------------------- |
| i    | 忽略大小写          |
| g    | 全局匹配            |
| gi   | 全局匹配+忽略大小写 |

### 2.4.2、正则匹配

```js
 /*
            正则的作用: 匹配、替换、提取
            1、作为正则对象来用,用来调用匹配方法  (匹配)
                正则对象.test(字符串)
                var reg = /^正则规则$/

                new RegExp(pattern, attributes);
                    pattern:一个字符串，指定了正则表达式的模式或其他正则表达式。
                    attributes:一个可选的字符串，包含属性“g”、“i”和“m”，分别用于指定全局匹配、区分大小写的匹配和多行匹配

                regexp.test(string)
                    string:要检测的字符串。
                    如果字符串string中含有与regexp匹配的文本，就返回true，否则返回false。

            2、作为正则参数来用,用来作为方法的参数  (替换、提取)
                字符串.replace(正则,字符串)
                字符串.replace(/正则规则/,字符串)
        */

// 电话号码
var tel_reg = /^\d{11}$/;
var tel = "12311111111";
console.log("电话号码是否符合规则:" + tel_reg.test(tel));

// 邮编
var postcode_reg = /^\d{6}$/;

// 验证日期 2012-5-01   
var date_reg = /^\d{4}(-\d{1,2}){1,2}$/;
// var date_reg = /^\d{4}-\d{1,2}-\d{1,2}$/;
var date1 = "2020-05";
var date2 = "2020-09-1";
var date3 = "2020";
console.log("日期是否符合规则:" + date_reg.test(date1));
console.log("日期是否符合规则:" + date_reg.test(date2));
console.log("日期是否符合规则:" + date_reg.test(date3));

// 邮箱 .com.cn
var email_reg = /^[A-Za-z0-9]{5,}@[a-z0-9]{2,5}(\.[a-z]{2,3}){1,2}$/;
// var email_reg = /^\w+@\w+\.\w+$/;
var email1 = "2@q.com";
var email2 = "zhangsan@163.com";
var email3 = "32132@qq.com";
var email4 = "zhangsan123@yahoo.com.cn";
console.log("邮箱是否符合规则:" + email_reg.test(email1));
console.log("邮箱是否符合规则:" + email_reg.test(email2));
console.log("邮箱是否符合规则:" + email_reg.test(email3));
console.log("邮箱是否符合规则:" + email_reg.test(email4));

// ip校验
var ip_reg = /^\d{1,3}(.\d{1,3}){3}$/;

// 用户名,8-20为字母、数子、下划线,不能全是数字
var userName_reg = /^(?![0-9]+$)\w{8,20}$/;
var userName = "12345678";
console.log("用户名是否符合规则:" + userName_reg.test(userName))
```

### 2.4.3、正则提取

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <script>
        // 1. 提取工资
        var str = "张三：1000，李四：5000，王五：8000。";
        var array = str.match(/\d+/g);
        console.log(array);

        // 2. 提取email地址
        var str =
            "123123@xx.com,fangfang@valuedopinions.cn 286669312@qq.com 2、emailenglish@emailenglish.englishtown.com 286669312@qq.com...";
        var array = str.match(/\w+@\w+\.\w+(\.\w+)?/g);
        console.log(array);

        // 3. 分组提取  
        // 3. 提取日期中的年部分  2015-5-10
        var dateStr = '2016-1-5';
        // 正则表达式中的()作为分组来使用，获取分组匹配到的结果用Regex.$1 $2 $3....来获取
        var reg = /^(\d{4})-\d{1,2}-\d{1,2}$/;
        if (reg.test(dateStr)) {
            console.log(RegExp.$1);
        }

        // 4. 提取邮件中的每一部分
        var reg = /^(\w+)@(\w+)\.(\w+)(\.\w+)?$/;
        var str = "123123@xx.com";
        if (reg.test(str)) {
            console.log(RegExp.$1);
            console.log(RegExp.$2);
            console.log(RegExp.$3);
        }
    </script>
</body>

</html>
```

### 2.4.4、正则替换

```js
// 1. 替换所有空白
var str = "   123AD  asadf   asadfasf  adf ";
str = str.replace(/\s/g,"xx");
console.log(str);

// 2. 替换所有,|，
var str = "abc,efg,123，abc,123，a";
str = str.replace(/,|，/g, ".");
console.log(str);
```

### 2.4.5、案例表单验证

#### 2.4.5.1、常规方式

```html
QQ号：<input type="text" id="txtQQ"><span></span><br>
邮箱：<input type="text" id="txtEMail"><span></span><br>
手机：<input type="text" id="txtPhone"><span></span><br>
生日：<input type="text" id="txtBirthday"><span></span><br>
姓名：<input type="text" id="txtName"><span></span><br>
```

```js
//获取文本框
var txtQQ = document.getElementById("txtQQ");
var txtEMail = document.getElementById("txtEMail");
var txtPhone = document.getElementById("txtPhone");
var txtBirthday = document.getElementById("txtBirthday");
var txtName = document.getElementById("txtName");

//
txtQQ.onblur = function () {
  //获取当前文本框对应的span
  var span = this.nextElementSibling;
  var reg = /^\d{5,12}$/;
  //判断验证是否成功
  if(!reg.test(this.value) ){
    //验证不成功
    span.innerText = "请输入正确的QQ号";
    span.style.color = "red";
  }else{
    //验证成功
    span.innerText = "";
    span.style.color = "";
  }
};

//txtEMail
txtEMail.onblur = function () {
  //获取当前文本框对应的span
  var span = this.nextElementSibling;
  var reg = /^\w+@\w+\.\w+(\.\w+)?$/;
  //判断验证是否成功
  if(!reg.test(this.value) ){
    //验证不成功
    span.innerText = "请输入正确的EMail地址";
    span.style.color = "red";
  }else{
    //验证成功
    span.innerText = "";
    span.style.color = "";
  }
};
```

#### 2.4.5.2、封装成函数

```js
 //获取文本框
var txtQQ = document.getElementById("txtQQ");
var txtEMail = document.getElementById("txtEMail");
var txtPhone = document.getElementById("txtPhone");
var txtBirthday = document.getElementById("txtBirthday");
var txtName = document.getElementById("txtName");

var qq_flag = false;
var email_flag = false;

// 封装共有函数
function check(element, reg, tips) {
    element.onfocus = function () {
        var nextSpan = this.nextElementSibling;
        nextSpan.innerHTML = "请输入您的" + tips;
        nextSpan.className = "";
    }

    element.onblur = function () {
        var val = this.value;
        var nextSpan = this.nextElementSibling;
        if (val.replace(/\s/g, "") === "") {
            nextSpan.innerHTML = tips + "不能为空";
            nextSpan.className = "error";
        } else {
            var reg_obj = reg;
            if (reg_obj.test(val)) {
                nextSpan.innerHTML = "格式正确";
                nextSpan.className = "correct";
                element.correct = true;
            } else {
                nextSpan.innerHTML = tips + "格式错误";
                nextSpan.className = "error";
            }
        }
    }
}

// 验证qq
var QQ_REG = /^\d{5,}$/;
check(txtQQ, QQ_REG, "QQ号码")

// 验证email
var email_reg = /^[A-Za-z0-9]{5,}@[a-z0-9]{2,5}(\.[a-z]{2,3}){1,2}$/;
check(txtEMail, email_reg, "邮箱地址")

// 验证手机号
var tel_reg = /^\d{11}$/;
check(txtPhone, tel_reg, "手机号码")



var f1 = document.getElementById("f1");
f1.onsubmit = function () {
    console.log(txtQQ.correct);
    if (!(txtQQ.correct && txtEMail.correct && txtPhone.correct)) {
        return false;
    }
}
```

#### 2.4.5.3、添加自定义验证属性对表单进行验证

```html
<form id="frm">
  QQ号：<input type="text" name="txtQQ" data-rule="qq"><span></span><br>
  邮箱：<input type="text" name="txtEMail" data-rule="email"><span></span><br>
  手机：<input type="text" name="txtPhone" data-rule="phone"><span></span><br>
  生日：<input type="text" name="txtBirthday" data-rule="date"><span></span><br>
  姓名：<input type="text" name="txtName" data-rule="cn"><span></span><br>
</form>
```

```js
// 所有的验证规则
var rules = [
  {
    name: 'qq',
    reg: /^\d{5,12}$/,
    tip: "请输入正确的QQ"
  },
  {
    name: 'email',
    reg: /^\w+@\w+\.\w+(\.\w+)?$/,
    tip: "请输入正确的邮箱地址"
  },
  {
    name: 'phone',
    reg: /^\d{11}$/,
    tip: "请输入正确的手机号码"
  },
  {
    name: 'date',
    reg: /^\d{4}-\d{1,2}-\d{1,2}$/,
    tip: "请输入正确的出生日期"
  },
  {
    name: 'cn',
    reg: /^[\u4e00-\u9fa5]{2,4}$/,
    tip: "请输入正确的姓名"
  }];

addCheck('frm');


//给文本框添加验证
function addCheck(formId) {
  var i = 0,
      len = 0,
      frm =document.getElementById(formId);
  len = frm.children.length;
  for (; i < len; i++) {
    var element = frm.children[i];
    // 表单元素中有name属性的元素添加验证
    if (element.name) {
      element.onblur = function () {
        // 使用dataset获取data-自定义属性的值
        var ruleName = this.dataset.rule;
        var rule =getRuleByRuleName(rules, ruleName);

        var span = this.nextElementSibling;
        //判断验证是否成功
        if(!rule.reg.test(this.value) ){
          //验证不成功
          span.innerText = rule.tip;
          span.style.color = "red";
        }else{
          //验证成功
          span.innerText = "";
          span.style.color = "";
        }
      }
    }
  }
}

// 根据规则的名称获取规则对象
function getRuleByRuleName(rules, ruleName) {
  var i = 0,
      len = rules.length;
  var rule = null;
  for (; i < len; i++) {
    if (rules[i].name == ruleName) {
      rule = rules[i];
      break;
    }
  }
  return rule;
}
```

## 2.5、常用正则汇总

### 2.5.1、校验数字的表达式

```js
数字：^[0-9]*$
n位的数字：^\d{n}$
至少n位的数字：^\d{n,}$
m-n位的数字：^\d{m,n}$
零和非零开头的数字：^(0|[1-9][0-9]*)$
非零开头的最多带两位小数的数字：^([1-9][0-9]*)+(\.[0-9]{1,2})?$
带1-2位小数的正数或负数：^(\-)?\d+(\.\d{1,2})$
正数、负数、和小数：^(\-|\+)?\d+(\.\d+)?$
有两位小数的正实数：^[0-9]+(\.[0-9]{2})?$
有1~3位小数的正实数：^[0-9]+(\.[0-9]{1,3})?$
非零的正整数：^[1-9]\d*$ 或 ^([1-9][0-9]*){1,3}$ 或 ^\+?[1-9][0-9]*$
非零的负整数：^\-[1-9][]0-9"*$ 或 ^-[1-9]\d*$
非负整数：^\d+$ 或 ^[1-9]\d*|0$
非正整数：^-[1-9]\d*|0$ 或 ^((-\d+)|(0+))$
非负浮点数：^\d+(\.\d+)?$ 或 ^[1-9]\d*\.\d*|0\.\d*[1-9]\d*|0?\.0+|0$
非正浮点数：^((-\d+(\.\d+)?)|(0+(\.0+)?))$ 或 ^(-([1-9]\d*\.\d*|0\.\d*[1-9]\d*))|0?\.0+|0$
正浮点数：^[1-9]\d*\.\d*|0\.\d*[1-9]\d*$ 或 ^(([0-9]+\.[0-9]*[1-9][0-9]*)|([0-9]*[1-9][0-9]*\.[0-9]+)|([0-9]*[1-9][0-9]*))$
负浮点数：^-([1-9]\d*\.\d*|0\.\d*[1-9]\d*)$ 或 ^(-(([0-9]+\.[0-9]*[1-9][0-9]*)|([0-9]*[1-9][0-9]*\.[0-9]+)|([0-9]*[1-9][0-9]*)))$
浮点数：^(-?\d+)(\.\d+)?$ 或 ^-?([1-9]\d*\.\d*|0\.\d*[1-9]\d*|0?\.0+|0)$
```

### 2.5.2、校验字符的表达式

```js
汉字：^[\u4e00-\u9fa5]{0,}$
英文和数字：^[A-Za-z0-9]+$ 或 ^[A-Za-z0-9]{4,40}$
长度为3-20的所有字符：^.{3,20}$
由26个英文字母组成的字符串：^[A-Za-z]+$
由26个大写英文字母组成的字符串：^[A-Z]+$
由26个小写英文字母组成的字符串：^[a-z]+$
由数字和26个英文字母组成的字符串：^[A-Za-z0-9]+$
由数字、26个英文字母或者下划线组成的字符串：^\w+$ 或 ^\w{3,20}$
中文、英文、数字包括下划线：^[\u4E00-\u9FA5A-Za-z0-9_]+$
中文、英文、数字但不包括下划线等符号：^[\u4E00-\u9FA5A-Za-z0-9]+$ 或 ^[\u4E00-\u9FA5A-Za-z0-9]{2,20}$
可以输入含有^%&',;=?$\"等字符：[^%&',;=?$\x22]+
禁止输入含有~的字符：[^~\x22]+
```

### 2.5.3、特殊需求表达式

```js
Email地址：^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$
域名：[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+\.?
InternetURL：[a-zA-z]+://[^\s]* 或 ^http://([\w-]+\.)+[\w-]+(/[\w-./?%&=]*)?$
手机号码：^(13[0-9]|14[5|7]|15[0|1|2|3|4|5|6|7|8|9]|18[0|1|2|3|5|6|7|8|9])\d{8}$
电话号码("XXX-XXXXXXX"、"XXXX-XXXXXXXX"、"XXX-XXXXXXX"、"XXX-XXXXXXXX"、"XXXXXXX"和"XXXXXXXX)：^(\(\d{3,4}-)|\d{3.4}-)?\d{7,8}$
国内电话号码(0511-4405222、021-87888822)：\d{3}-\d{8}|\d{4}-\d{7}
电话号码正则表达式（支持手机号码，3-4位区号，7-8位直播号码，1－4位分机号）: ((\d{11})|^((\d{7,8})|(\d{4}|\d{3})-(\d{7,8})|(\d{4}|\d{3})-(\d{7,8})-(\d{4}|\d{3}|\d{2}|\d{1})|(\d{7,8})-(\d{4}|\d{3}|\d{2}|\d{1}))$)
身份证号(15位、18位数字)，最后一位是校验位，可能为数字或字符X：(^\d{15}$)|(^\d{18}$)|(^\d{17}(\d|X|x)$)
帐号是否合法(字母开头，允许5-16字节，允许字母数字下划线)：^[a-zA-Z][a-zA-Z0-9_]{4,15}$
密码(以字母开头，长度在6~18之间，只能包含字母、数字和下划线)：^[a-zA-Z]\w{5,17}$
强密码(必须包含大小写字母和数字的组合，不能使用特殊字符，长度在 8-10 之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])[a-zA-Z0-9]{8,10}$
强密码(必须包含大小写字母和数字的组合，可以使用特殊字符，长度在8-10之间)：^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,10}$
日期格式：^\d{4}-\d{1,2}-\d{1,2}
一年的12个月(01～09和1～12)：^(0?[1-9]|1[0-2])$
一个月的31天(01～09和1～31)：^((0?[1-9])|((1|2)[0-9])|30|31)$

钱的输入格式：
    有四种钱的表示形式我们可以接受:"10000.00" 和 "10,000.00", 和没有 "分" 的 "10000" 和 "10,000"：^[1-9][0-9]*$
    这表示任意一个不以0开头的数字,但是,这也意味着一个字符"0"不通过,所以我们采用下面的形式：^(0|[1-9][0-9]*)$
    一个0或者一个不以0开头的数字.我们还可以允许开头有一个负号：^(0|-?[1-9][0-9]*)$
    这表示一个0或者一个可能为负的开头不为0的数字.让用户以0开头好了.把负号的也去掉,因为钱总不能是负的吧。下面我们要加的是说明可能的小数部分：^[0-9]+(.[0-9]+)?$
    必须说明的是,小数点后面至少应该有1位数,所以"10."是不通过的,但是 "10" 和 "10.2" 是通过的：^[0-9]+(.[0-9]{2})?$
    这样我们规定小数点后面必须有两位,如果你认为太苛刻了,可以这样：^[0-9]+(.[0-9]{1,2})?$
    这样就允许用户只写一位小数.下面我们该考虑数字中的逗号了,我们可以这样：^[0-9]{1,3}(,[0-9]{3})*(.[0-9]{1,2})?$
    1到3个数字,后面跟着任意个 逗号+3个数字,逗号成为可选,而不是必须：^([0-9]+|[0-9]{1,3}(,[0-9]{3})*)(.[0-9]{1,2})?$
    备注：这就是最终结果了,别忘了"+"可以用"*"替代如果你觉得空字符串也可以接受的话(奇怪,为什么?)最后,别忘了在用函数时去掉去掉那个反斜杠,一般的错误都在这里
    
xml文件：^([a-zA-Z]+-?)+[a-zA-Z0-9]+\\.[x|X][m|M][l|L]$
中文字符的正则表达式：[\u4e00-\u9fa5]
双字节字符：[^\x00-\xff] (包括汉字在内，可以用来计算字符串的长度(一个双字节字符长度计2，ASCII字符计1))
空白行的正则表达式：\n\s*\r (可以用来删除空白行)
HTML标记的正则表达式：<(\S*?)[^>]*>.*?|<.*? /> ( 首尾空白字符的正则表达式：^\s*|\s*$或(^\s*)|(\s*$) (可以用来删除行首行尾的空白字符(包括空格、制表符、换页符等等)，非常有用的表达式)
腾讯QQ号：[1-9][0-9]{4,} (腾讯QQ号从10000开始)
中国邮政编码：[1-9]\d{5}(?!\d) (中国邮政编码为6位数字)
IP地址：((?:(?:25[0-5]|2[0-4]\\d|[01]?\\d?\\d)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d?\\d))
```

正则表达式在线测试：https://c.runoob.com/front-end/854

<a id="p6-3"></a>
# 三、JavaScript面向对象编程

## 3.1、面向对象概述

### 3.1.1、什么是对象

> Everything is object （万物皆对象）

![](images05_higher/微信截图_20200725105825.png)

对象到底是什么，我们可以从两次层次来理解。

**(1) 对象是单个事物的抽象。**

一本书、一辆汽车、一个人都可以是对象，一个数据库、一张网页、一个与远程服务器的连接也可以是对象。当实物被抽象成对象，实物之间的关系就变成了对象之间的关系，从而就可以模拟现实情况，针对对象进行编程。

**(2) 对象是一个容器，封装了属性（property）和方法（method）。**

属性是对象的状态，方法是对象的行为（完成某种任务）。比如，我们可以把动物抽象为animal对象，使用“属性”记录具体是那一种动物，使用“方法”表示动物的某种行为（奔跑、捕猎、休息等等）。

在实际开发中，对象是一个抽象的概念，可以将其简单理解为：**数据集或功能集**。

ECMAScript-262 把对象定义为：**无序属性的集合，其属性可以包含基本值、对象或者函数**。

严格来讲，这就相当于说对象是一组没有特定顺序的值。对象的每个属性或方法都有一个名字，而每个名字都映射到一个值。

提示：每个对象都是基于一个引用类型创建的，这些类型可以是系统内置的原生类型，也可以是开发人员自定义的类型。

### 3.1.2、什么是面向对象

> 面向对象不是新的东西，它只是过程式代码的一种高度封装，目的在于提高代码的开发效率和可维 护性。

![](images05_higher/微信截图_20200725114532.png)

面向对象编程 —— Object Oriented Programming，简称 OOP ，是一种编程开发思想。

它将真实世界各种复杂的关系，抽象为一个个对象，然后由对象之间的分工与合作，完成对真实世界的模拟。

在面向对象程序开发思想中，每一个对象都是功能中心，具有明确分工，可以完成接受信息、处理数据、发出信息等任务。

因此，面向对象编程具有灵活、代码可复用、高度模块化等特点，容易维护和开发，比起由一系列函数或指令组成的传统的过程式编程（procedural programming），更适合多人合作的大型软件项目。

面向对象与面向过程： 

- 面向过程就是亲力亲为，事无巨细，面面俱到，步步紧跟，有条不紊
- 面向对象就是找一个对象，指挥得结果
- 面向对象将执行者转变成指挥者
- 面向对象不是面向过程的替代，而是面向过程的封装

面向对象的特性：

- 封装性 
- 继承性
- [多态性]抽象

扩展阅读：

- [维基百科 - 面向对象程序设计](https://zh.wikipedia.org/wiki/%E9%9D%A2%E5%90%91%E5%AF%B9%E8%B1%A1%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1)
- [知乎：如何用一句话说明什么是面向对象思想？](https://www.zhihu.com/question/19854505)
- [知乎：什么是面向对象编程思想？](https://www.zhihu.com/question/31021366)

### 3.1.3、程序中面向对象的基本体现

在 JavaScript 中，所有数据类型都可以视为对象，当然也可以自定义对象。

我们以一个例子来说明面向过程和面向对象在程序流程上的不同之处。

假设我们要处理学生的成绩表，为了表示一个学生的成绩，面向过程的程序可以用一个对象表示：

```javascript
var stu1 = {name: 'zs', subject: '语文', score: 90};
var stu2 = {name: 'ls', subject: '语文', score: 80};
```

而处理学生成绩可以通过函数实现，比如打印学生的成绩：

```javascript
console.log(stu1.name, stu1.subject, stu1.score);

console.log(stu2.name, stu2.subject, stu2.score);
```

如果采用面向对象的程序设计思想，我们首选思考的不是程序的执行流程，而是 `Student` 这种数据类型应该被视为一个对象，这个对象拥有 `name` 和 `score` 这两个属性（Property）。

如果要打印一个学生的成绩，首先必须创建出这个学生对应的对象，然后，给对象发一个 `printScore` 消息，让对象自己把自己的数据打印出来。

抽象数据行为模板（Class）：

```javascript
function Student(name, score) {
  this.name = name;
  this.score = score;
  this.printScore = function() {
    console.log('姓名：' + this.name + '  ' + '成绩：' + this.score);
  }
}
```

根据模板创建具体实例对象（Instance）：

```javascript
var std1 = new Student('Michael', 98)
var std2 = new Student('Bob', 81)
```

实例对象具有自己的具体行为（给对象发消息）：

```javascript
std1.printScore() // => 姓名：Michael  成绩：98
std2.printScore() // => 姓名：Bob  成绩 81
```

面向对象的设计思想是从自然界中来的，因为在自然界中，类（Class）和实例（Instance）的概念是很自然的。

Class 是一种抽象概念，比如我们定义的 Class——Student ，是指学生这个概念，而实例（Instance）则是一个个具体的 Student ，比如， Michael 和 Bob 是两个具体的 Student 。

所以，面向对象的设计思想是：

- 抽象出 Class(构造函数)
- 根据 Class(构造函数) 创建 Instance
- 指挥 Instance 得结果

面向对象的抽象程度又比函数要高，因为一个 Class 既包含数据，又包含操作数据的方法。

## 3.2、创建对象

### 3.2.1、new Object()创建对象

```js
var person = new Object()
person.name = 'Jack'
person.age = 18

person.sayName = function () {
  console.log(this.name)
}
```

每次创建通过 `new Object()` 比较麻烦，所以可以通过它的简写形式对象字面量来创建：

### 3.2.2、对象字面量

```js
var person = {
  name: 'Jack',
  age: 18,
  sayName: function () {
    console.log(this.name)
  }
}
```

对于上面的写法固然没有问题，但是假如我们要生成两个 `person` 实例对象呢？代码太过冗余，重复性太高。

### 3.2.3、工厂函数创建对象

我们可以写一个函数，解决代码重复问题：

```js
function createPerson (name, age) {
  return {
    name: name,
    age: age,
    sayName: function () {
      console.log(this.name)
    }
  }
}
```

然后生成实例对象：

```javascript
var p1 = createPerson('Jack', 18)
var p2 = createPerson('Mike', 18)
```

这样封装确实爽多了，通过工厂模式我们解决了创建多个相似对象代码冗余的问题，
但却没有解决对象识别的问题（即怎样知道一个对象的类型）。

### 3.2.4、构造函数

#### 3.2.4.1、构造函数语法

一种更优雅的工厂函数就是下面这样，构造函数：

```js
function Person (name, age) {
  this.name = name
  this.age = age
  this.sayName = function () {
    console.log(this.name)
  }
}

var p1 = new Person('Jack', 18)
p1.sayName() // => Jack

var p2 = new Person('Mike', 23)
p2.sayName() // => Mike
```

#### 3.2.4.2、构造函数分析

在上面的示例中，`Person()` 函数取代了 `createPerson()` 函数，但是实现效果是一样的。
这是为什么呢？

我们注意到，`Person()` 中的代码与 `createPerson()` 有以下几点不同之处：

- 没有显示的创建对象
- 直接将属性和方法赋给了 `this` 对象
- 没有 `return` 语句
- 函数名使用的是大写的 `Person`

而要创建 `Person` 实例，则必须使用 `new` 操作符。

以这种方式调用构造函数会经历以下 4 个步骤：

1. 创建一个新对象
2. 将构造函数的作用域赋给新对象（因此 this 就指向了这个新对象）
3. 执行构造函数中的代码
4. 返回新对象

下面是具体的伪代码：

```javascript
function Person (name, age) {
  // 当使用 new 操作符调用 Person() 的时候，实际上这里会先创建一个对象
  // var instance = {}
  // 然后让内部的 this 指向 instance 对象
  // this = instance
  // 接下来所有针对 this 的操作实际上操作的就是 instance

  this.name = name
  this.age = age
  this.sayName = function () {
    console.log(this.name)
  }

  // 在函数的结尾处会将 this 返回，也就是 instance
  // return this
}
```

#### 3.2.4.3、构造函数和实例对象的关系

使用构造函数的好处不仅仅在于代码的简洁性，更重要的是我们可以识别对象的具体类型了。

在每一个实例对象中同时有一个 `constructor` 属性，该属性指向创建该实例的构造函数：

```javascript
console.log(p1.constructor === Person) // => true
console.log(p2.constructor === Person) // => true
console.log(p1.constructor === p2.constructor) // => true
```

对象的 `constructor` 属性最初是用来标识对象类型的，
但是，如果要检测对象的类型，还是使用 `instanceof` 操作符更可靠一些：

```javascript
console.log(p1 instanceof Person) // => true
console.log(p2 instanceof Person) // => true
```

总结：

- 构造函数是根据具体的事物抽象出来的抽象模板
- 实例对象是根据抽象的构造函数模板得到的具体实例对象
- 每一个实例对象都具有一个 `constructor` 属性，指向创建该实例的构造函数
  - 注意： `constructor` 是实例的属性的说法不严谨，具体后面的原型会讲到
- 可以通过实例的 `constructor` 属性判断实例和构造函数之间的关系
  - 注意：这种方式不严谨，推荐使用 `instanceof` 操作符，后面学原型会解释为什么

#### 3.2.4.4、构造函数的问题

使用构造函数带来的最大的好处就是创建对象更方便了，但是其本身也存在一个浪费内存的问题：

```javascript
function Person (name, age) {
  this.name = name
  this.age = age
  this.type = 'human'
  this.sayHello = function () {
    console.log('hello ' + this.name)
  }
}

var p1 = new Person('Tom', 18)
var p2 = new Person('Jack', 16)
```

在该示例中，从表面上好像没什么问题，但是实际上这样做，有一个很大的弊端。
那就是对于每一个实例对象，`type` 和 `sayHello` 都是一模一样的内容，
每一次生成一个实例，都必须为重复的内容，多占用一些内存，如果实例对象很多，会造成极大的内存浪费。

```javascript
console.log(p1.sayHello === p2.sayHello) // => false
```

对于这种问题我们可以把需要共享的函数定义到构造函数外部：

```javascript
function sayHello () {
  console.log('hello ' + this.name)
}

function Person (name, age) {
  this.name = name
  this.age = age
  this.type = 'human'
  this.sayHello = sayHello
}

var p1 = new Person('Top', 18)
var p2 = new Person('Jack', 16)

console.log(p1.sayHello === p2.sayHello) // => true
```

这样确实可以了，但是如果有多个需要共享的函数的话就会造成全局命名空间冲突的问题。

你肯定想到了可以把多个函数放到一个对象中用来避免全局命名空间冲突的问题：

```javascript
var fns = {
  sayHello: function () {
    console.log('hello ' + this.name)
  },
  sayAge: function () {
    console.log(this.age)
  }
}

function Person (name, age) {
  this.name = name
  this.age = age
  this.type = 'human'
  this.sayHello = fns.sayHello
  this.sayAge = fns.sayAge
}

var p1 = new Person('lpz', 18)
var p2 = new Person('Jack', 16)

console.log(p1.sayHello === p2.sayHello) // => true
console.log(p1.sayAge === p2.sayAge) // => true
```

至此，我们利用自己的方式基本上解决了构造函数的内存浪费问题。

但是代码看起来还是那么的格格不入，那有没有更好的方式呢？

## 3.3、原型

### 3.3.1、更好的解决方案： `prototype`

JavaScript 规定，每一个构造函数都有一个 `prototype` 属性，指向另一个对象。

这个对象的所有属性和方法，都会被构造函数的所拥有。

这也就意味着，我们可以把所有对象实例需要共享的属性和方法直接定义在 `prototype` 对象上。

```javascript
function Person (name, age) {
  this.name = name
  this.age = age
}

console.log(Person.prototype)

Person.prototype.type = 'human'

Person.prototype.sayName = function () {
  console.log(this.name)
}

var p1 = new Person(...)
var p2 = new Person(...)

console.log(p1.sayName === p2.sayName) // => true
```

这时所有实例的 `type` 属性和 `sayName()` 方法，其实都是同一个内存地址，指向 `prototype` 对象，因此就提高了运行效率。

### 3.3.2、构造函数、实例、原型三者之间的关系

![](images05_higher/微信截图_20200725141548.png)

任何函数都具有一个 `prototype` 属性，该属性是一个对象。

```javascript
function F () {}
console.log(F.prototype) // => object

F.prototype.sayHi = function () {
  console.log('hi!')
}
```

构造函数的 `prototype` 对象默认都有一个 `constructor` 属性，指向 `prototype` 对象所在函数。

```javascript
console.log(F.prototype.constructor === F) // => false
```

通过构造函数得到的实例对象内部会包含一个指向构造函数的 `prototype` 对象的指针 `__proto__`。

```javascript
var instance = new F()
console.log(instance.__proto__ === F.prototype) // => true
```

<p class="tip">
  `__proto__` 是非标准属性。
</p>

实例对象可以直接访问原型对象成员。

```javascript
instance.sayHi() // => hi!
```

总结：

- 任何函数都具有一个 `prototype` 属性，该属性是一个对象
- 构造函数的 `prototype` 对象默认都有一个 `constructor` 属性，指向 `prototype` 对象所在函数
- 通过构造函数得到的实例对象内部会包含一个指向构造函数的 `prototype` 对象的指针 `__proto__`
- 所有实例都直接或间接继承了原型对象的成员

### 3.3.3、属性成员的搜索原则：原型链

了解了 **构造函数-实例-原型对象** 三者之间的关系后，接下来我们来解释一下为什么实例对象可以访问原型对象中的成员。

每当代码读取某个对象的某个属性时，都会执行一次搜索，目标是具有给定名字的属性

- 搜索首先从对象实例本身开始
- 如果在实例中找到了具有给定名字的属性，则返回该属性的值
- 如果没有找到，则继续搜索指针指向的原型对象，在原型对象中查找具有给定名字的属性
- 如果在原型对象中找到了这个属性，则返回该属性的值

也就是说，在我们调用 `person1.sayName()` 的时候，会先后执行两次搜索：

- 首先，解析器会问：“实例 person1 有 sayName 属性吗？”答：“没有。
- ”然后，它继续搜索，再问：“ person1 的原型有 sayName 属性吗？”答：“有。
- ”于是，它就读取那个保存在原型对象中的函数。
- 当我们调用 person2.sayName() 时，将会重现相同的搜索过程，得到相同的结果。

而这正是多个对象实例共享原型所保存的属性和方法的基本原理。

总结：

- 先在自己身上找，找到即返回
- 自己身上找不到，则沿着原型链向上查找，找到即返回
- 如果一直到原型链的末端还没有找到，则返回 `undefined`

### 3.3.4、实例对象读写原型对象成员

读取：

- 先在自己身上找，找到即返回
- 自己身上找不到，则沿着原型链向上查找，找到即返回
- 如果一直到原型链的末端还没有找到，则返回 `undefined`

值类型成员写入（`实例对象.值类型成员 = xx`）：

- 当实例期望重写原型对象中的某个普通数据成员时实际上会把该成员添加到自己身上
- 也就是说该行为实际上会屏蔽掉对原型对象成员的访问

引用类型成员写入（`实例对象.引用类型成员 = xx`）：

- 同上

复杂类型修改（`实例对象.成员.xx = xx`）：

- 同样会先在自己身上找该成员，如果自己身上找到则直接修改
- 如果自己身上找不到，则沿着原型链继续查找，如果找到则修改
- 如果一直到原型链的末端还没有找到该成员，则报错（`实例对象.undefined.xx = xx`）

```js
function Person(name, age) {
    this.name = name
    this.age = age
}

console.log(Person.prototype)

Person.prototype.type = 'human'
Person.prototype.evr = {
    breathe: "氧气",
    drink: "水"
}

Person.prototype.sayName = function () {
    console.log(this.name)
}

var p1 = new Person("zhangsan", 12);
var p2 = new Person("lis", 11);

p1.type = "cat"
console.log(p1.type); // cat
console.log(p1.__proto__.type) // human

// p1.evr = "xx";
// console.log(p1.evr); // xx
// console.log(p1.__proto__.evr) // {breathe: "氧气", drink: "水"}

p1.evr.drink = "纯净水";
console.log(p1.evr); // {breathe: "氧气", drink: "纯净水"}
console.log(p1.__proto__.evr) // {breathe: "氧气", drink: "纯净水"}
```

### 3.3.5、更简单的原型语法

我们注意到，前面例子中每添加一个属性和方法就要敲一遍 `Person.prototype` 。
为减少不必要的输入，更常见的做法是用一个包含所有属性和方法的对象字面量来重写整个原型对象：

```javascript
function Person (name, age) {
  this.name = name
  this.age = age
}

Person.prototype = {
  type: 'human',
  sayHello: function () {
    console.log('我叫' + this.name + '，我今年' + this.age + '岁了')
  }
}
```

在该示例中，我们将 `Person.prototype` 重置到了一个新的对象。

这样做的好处就是为 `Person.prototype` 添加成员简单了，但是也会带来一个问题，那就是原型对象丢失了 `constructor` 成员。

所以，我们为了保持 `constructor` 的指向正确，建议的写法是：

```javascript
function Person (name, age) {
  this.name = name
  this.age = age
}

Person.prototype = {
  constructor: Person, // => 手动将 constructor 指向正确的构造函数
  type: 'human',
  sayHello: function () {
    console.log('我叫' + this.name + '，我今年' + this.age + '岁了')
  }
}
```

### 3.3.5、原生对象的原型

<p class="tip">
  所有函数都有 prototype 属性对象。
</p>

- Object.prototype
- Function.prototype
- Array.prototype
- String.prototype
- Number.prototype
- Date.prototype
- ...

练习：为数组对象和字符串对象扩展原型方法。

```js
var array = [5, 4, 1, 8];

Array.prototype.getSum = function () {
    // 求数组中所有偶数的和
    var sum = 0;
    for (var i = 0; i < this.length; i++) {
        if (this[i] % 2 === 0) {
            sum += this[i];
        }
    }
    return sum;
}
// 数组或者String 中的prototype是不可以修改的
// Array.prototype = {
//   getSum: function () {
//      // 求数组中所有偶数的和
//     var sum = 0;
//     for (var i = 0; i < this.length; i++) {
//       if (this[i] % 2 === 0) {
//         sum += this[i];
//       }
//     }
//     return sum;
//   }
// }

console.log(array.getSum());
```

### 3.3.6、原型对象使用建议

- 私有成员（一般就是非函数成员）放到构造函数中
- 共享成员（一般就是函数）放到原型对象中
- 如果重置了 `prototype` 记得修正 `constructor` 的指向

## 3.4、继承

### 3.4.1、什么是继承

​	继承是面向对象编程中的一个重要概念，通过继承可以使子类的实例使用在父类中定义的属性和方法。

### 3.4.2、继承的实现方式

**对象字面量继承**

```js
var wjl = {
    name: '王健林',
    money: 10000000,
    cars: ['玛莎拉蒂', '特斯拉'],
    houses: ['别墅', '大别墅'],
    play: function () {
        console.log('打高尔夫');
    }
}

var wsc = {
    name: '王思聪'
}

// // 复制对象的成员给另一个对象
// for (var key in wjl) {
//   // 不给wsc复制同名的属性
//   if (wsc[key]) {
//     continue;
//   }
//   wsc[key] = wjl[key];
// }

// console.log(wsc);

// 对象的拷贝
// 复制对象的成员给另一个对象
function extend(parent, child) {
    for (var key in parent) {
        // 不给wsc复制同名的属性
        if (child[key]) {
            continue;
        }
        child[key] = parent[key];
    }
}

extend(wjl, wsc);

console.log(wsc);
```

**构造函数的属性继承：借用构造函数**

```javascript
function Person (name, age) {
  this.type = 'human'
  this.name = name
  this.age = age
}

function Student (name, age) {
  // 借用构造函数继承属性成员 
  // call()是改变函数中的this，直接调用函数
  Person.call(this, name, age)
}

var s1 = new Student('张三', 18)
console.log(s1.type, s1.name, s1.age) // => human 张三 18
```

**构造函数的原型方法继承：拷贝继承（for-in）**

```javascript
function Person(name, age) {
    this.type = 'human'
    this.name = name
    this.age = age
}

Person.prototype.sayName = function () {
    console.log('hello ' + this.name)
}

function Student(name, age) {
    Person.call(this, name, age)
}

// 原型对象拷贝继承原型对象成员
for (var key in Person.prototype) {
    Student.prototype[key] = Person.prototype[key]
}

var s1 = new Student('张三', 18)

s1.sayName() // => hello 张三
```

**另一种继承方式：原型继承**

```javascript
 function Person(name, age) {
     this.type = 'human'
     this.name = name
     this.age = age
 }

Person.prototype.sayName = function () {
    console.log('hello ' + this.name)
}

function Student(name, age) {
    Person.call(this, name, age)
}

// 利用原型的特性实现继承
Student.prototype = new Person();
Student.prototype.constructor = Student;

var s1 = new Student('张三', 18)

console.log(s1.type) // => human

s1.sayName() // => hello 张三
```

<a id="p6-4"></a>
# 四、函数进阶

## 4.1、函数回顾

### 4.1.1、函数的定义方式

- 函数声明

```js
function foo () {

}
```

- 函数表达式

```js
var foo = function () {

}
```

**函数声明与函数表达式的区别**

- 函数声明必须有名字
- 函数声明会函数提升，在预解析阶段就已创建，声明前后都可以调用
- 函数表达式类似于变量赋值
- 函数表达式可以没有名字，例如匿名函数
- 函数表达式没有变量提升，在执行阶段创建，必须在表达式执行之后才可以调用

### 4.1.2、函数的调用方式

- 普通函数

```js
function foo () {

}

foo()
```

- 构造函数

```js
function Person (name,age) {
	thia.name = name;
	this.age = age
	...
}

new Person();
```

- 对象方法

```js
var obj = {
    name:"zhangsan",
    age:12,
    eat:function(){
        ..
    }
}

obj.eat();
```

## 4.2、函数内 `this` 指向的不同场景

函数的调用方式决定了 `this` 指向的不同：

| 调用方式     | 非严格模式     | 备注                         |
| ------------ | -------------- | ---------------------------- |
| 普通函数调用 | window         | 严格模式下是 undefined       |
| 构造函数调用 | 实例对象       | 原型方法中 this 也是实例对象 |
| 对象方法调用 | 该方法所属对象 | 紧挨着的对象                 |
| 事件绑定方法 | 绑定事件对象   |                              |
| 定时器函数   | window         |                              |

这就是对函数内部 this 指向的基本整理，写代码写多了自然而然就熟悉了。

```html
<ul id="ul1">
    <li>我是第1个li</li>
    <li>我是第2个li</li>
    <li>我是第3个li</li>
    <li>我是第4个li</li>
    <li>我是第5个li</li>
</ul>
<script>
    // 普通函数内部this指向
    // 这是全局函数,挂载在window上
    var a = 100;

    function fn1() {
        // 所以在这个函数内部使用this,指向的就是window
        console.log(this, this.a);
    }
    fn1();

    console.log("-----------------------------");
    // 构造函数调用,构造函数里面的this,是实例对象
    // 当我们使用new来调用构造函数的时候,会隐式创建一个对象,然后把这个对象给this,最后把this反馈出去
    function Person(name, age) {
        this.name = name;
        this.age = age;
        this.sayHello = function () {
            console.log(this.name + "说:Hello");
        }
    }

    var p1 = new Person("张三", 18);
    p1.sayHello();

    console.log("-----------------------------");
    // 对象方法调用，this就是该方法所属对象
    var obj = {
        name: "李四",
        // this代表的是window
        age: a,
        // 对象方法里面的this,代表的就是方法所属对象
        sayHello: function () {
            console.log(this.name + "说:Hello");
        }
    }

    obj.sayHello();
    console.log(obj.age);

    console.log("-----------------------------");
    // 事件绑定方法
    // document.onclick = function () {
    //     // 事件函数里面的this,代表事件的当前对象
    //     console.log(this)
    // }

    // 定时器函数
    setTimeout(function () {
        console.log(this);
    }, 1000)


    // 获取li的下标
    var lis = document.querySelectorAll("#ul1>li");
    for (var i = 0; i < lis.length; i++) {
        var li = lis[i];
        li.index = i;

        //在鼠标函数里面,this是点击的li
        li.onclick = function () {
            // 通过变量来保存this
            var _this = this;

            // 1s之后,输出li的下标
            setTimeout(function () {
                // 因为在定时器里面,this是window
                console.log(_this.index);
            }, 1000)
        }
    }
</script>
```

## 4.3、call、apply、bind

先看明白下面：

**例子1：**

```js
// window下面定义的两个全局变量
var name = "小王",
    age = 17;

var obj = {
    name: "小张",
    // 这里的this是window
    objAge: this.age,
    myFun: function () {
        // 对象函数里面的this就是函数所在的对象，obj
        console.log(this.name + "年龄" + this.age);
    }
}

console.log(obj.objAge); // 17
obj.myFun(); // 小张年龄 undefined
```

**例子2:**

```js
var fav = "小张";

function shows() {
    console.log(this.fav)
}

shows(); // 小张
```

​	那了解了函数 this 指向的不同场景之后，我们知道有些情况下我们为了使用某种特定环境的 this 引用，
这时候时候我们就需要采用一些特殊手段来处理了，例如我们经常在定时器外部备份 this 引用，然后在定时器函数内部使用外部 this 的引用。

​	然而实际上对于这种做法我们的 JavaScript 为我们专门提供了一些函数方法用来帮我们更优雅的处理函数内部 this 指向问题。

​	这就是接下来我们要学习的 call、apply、bind 三个函数方法。

### 4.3.1、语法

**call讲解：**

`call()` 方法调用一个函数, 其具有一个指定的 `this` 值和分别地提供的参数(参数的列表)。

注意：该方法的作用和 `apply()` 方法类似，只有一个区别，就是 `call()` 方法接受的是若干个参数的列表，而 `apply()` 方法接受的是一个包含多个参数的数组。


语法：

```javascript
fun.call(thisArg[, arg1[, arg2[, ...]]])
```

参数：

- `thisArg`
  - 在 fun 函数运行时指定的 this 值
  - 如果指定了 null 或者 undefined 则内部 this 指向 window
- `arg1, arg2, ...`
  - 指定的参数列表

**apply**

`apply()` 方法调用一个函数, 其具有一个指定的 `this` 值，以及作为一个数组（或类似数组的对象）提供的参数。

<p class="danger">
  注意：该方法的作用和 `call()` 方法类似，只有一个区别，就是 `call()` 方法接受的是若干个参数的列表，而 `apply()` 方法接受的是一个包含多个参数的数组。
</p>

语法：

```javascript
fun.apply(thisArg, [argsArray])
```

参数：

- `thisArg`
- `argsArray`

`apply()` 与 `call()` 非常相似，不同之处在于提供参数的方式。
`apply()` 使用参数数组而不是一组参数列表。例如：

```javascript
fun.apply(this, ['eat', 'bananas'])
```

**bind**

bind() 函数会创建一个新函数（称为绑定函数），新函数与被调函数（绑定函数的目标函数）具有相同的函数体（在 ECMAScript 5 规范中内置的call属性）。
当目标函数被调用时 this 值绑定到 bind() 的第一个参数，该参数不能被重写。绑定函数被调用时，bind() 也接受预设的参数提供给原函数。
一个绑定函数也能使用new操作符创建对象：这种行为就像把原函数当成构造器。提供的 this 值被忽略，同时调用时的参数被提供给模拟函数。

语法：

```javascript
fun.bind(thisArg[, arg1[, arg2[, ...]]])
```

参数：

- thisArg
  - 当绑定函数被调用时，该参数会作为原函数运行时的 this 指向。当使用new 操作符调用绑定函数时，该参数无效。
- arg1, arg2, ...
  - 当绑定函数被调用时，这些参数将置于实参之前传递给被绑定的方法。

返回值：

​	返回由指定的this值和初始化参数改造的原函数拷贝。

### 4.3.2、测试

**1、call()、apply()、bind() 都是用来重定义 this 这个对象的！**

```js
var name = "小王",
    age = 17;

var obj = {
    name: "小张",
    objAge: this.age,
    myFun: function () {
        console.log(this.name + "年龄" + this.age);
    }
}

var db = {
    name: "德邦总管",
    age: 99
}

obj.myFun.call(db); // 德邦总管年龄 99
obj.myFun.apply(db); // 德邦总管年龄 99
obj.myFun.bind(db)(); // 德邦总管年龄 99
```

以上出了 bind 方法后面多了个 () 外 ，结果返回都一致！

由此得出结论，bind 返回的是一个新的函数，你必须调用它才会被执行。

**2、对比call 、bind 、 apply 传参情况下**

```js
var name = "小王",
    age = 17;

var obj = {
    name: "小张",
    objAge: this.age,
    myFun: function (fm, to) {
        console.log(this.name + " 年龄 " + this.age, " 来自 " + fm + " 去往 " + to);
    }
}

var db = {
    name: "德邦总管",
    age: 99
}

obj.myFun.call(db, '成都', '上海'); // 德邦总管 年龄 99  来自 成都去往上海
obj.myFun.apply(db, ['成都', '上海']); // 德邦总管 年龄 99  来自 成都去往上海  
obj.myFun.bind(db, '成都', '上海')(); // 德邦总管 年龄 99  来自 成都去往上海
obj.myFun.bind(db, ['成都', '上海'])(); // 德邦总管 年龄 99  来自 成都, 上海去往 undefined
```

### 4.3.3、应用

**call的应用**

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>

<body>
    <span>1</span>
    <span>2</span>
    <span>3</span>
    <script>
        // 获取到页面的所有span,得到HTMLCollection,无论是HTMLCollection还是NodeList,我们都称之为伪数组
        // 伪数组本质是一个对象,只是模拟的数组的特性
        // 用下标作为对象的key,并且也提供的length
        var spans = document.getElementsByTagName("span");
        console.log(spans)
        // spans.shift(); // spans.shift is not a function

        var arr = ["zhangsan", "lis", "wangwu"]
        console.log(arr)

        // getElementsByTagName()
        // 伪数组
        var obj = {
            0: 100,
            1: 10,
            2: 11,
            3: 20,
            length: 4
        };

        console.log("伪数组下标2的值:" + obj['2']);

        // 向伪数组添加一个值
        // obj.push(30); // obj.push is not a function

        // obj['4'] = 30;
        // obj.length++;

        // console.log(obj);

        // push(参数)   向当前数组的末尾添加一个参数
        // push()   this[最后下标+1] = 值;  length++;
        Array.prototype.push.call(obj, 330); // this[最后下标+1] = 值;
        // Array.prototype.splice.call(obj, 0, 3);

        console.log(obj);

        var obj = {
            name: 'zs'
        };

        console.log(obj.toString()); // [object object]

        var arr = [5, 9];
        console.log(arr.toString()); // 5,9

        console.log(Object.prototype.toString.call(arr));
    </script>
</body>

</html>
```

**apply应用**

```js
// fn.apply(,[])

// Math.max(3, 5, 6);

var arr = [5, 10, 1, 3, 6];
// Math.max不能求数组中的最大值
// console.log(Math.max(arr));

console.log(Math.max.apply(null, arr));
console.log(Math.max.apply(Math, arr));


// console.log(1, 2, 3);
// console.log(arr);
```

**bind应用**

```js
// 3 bind的应用
function Bloomer() {
    this.petalCount = Math.ceil(Math.random() * 12) + 1;
}

// 1秒后调用declare函数
Bloomer.prototype.bloom = function () {
    window.setTimeout(this.declare.bind(this), 1000);
};

Bloomer.prototype.declare = function () {
    console.log('我有 ' + this.petalCount + ' 朵花瓣!');
};

var test = new Bloomer();

test.bloom();
```

```html
<ul id="ul1">
    <li>我是第1个li</li>
    <li>我是第2个li</li>
    <li>我是第3个li</li>
    <li>我是第4个li</li>
    <li>我是第5个li</li>
</ul>

<script>
	// 获取li的下标
    var lis = document.querySelectorAll("#ul1>li");
    for (var i = 0; i < lis.length; i++) {
        var li = lis[i];
        li.index = i;

        //在鼠标函数里面,this是点击的li
        li.onclick = function () {
            // // 通过变量来保存this
            // var _this = this;

            // 1s之后,输出li的下标
            setTimeout(function () {
                // 因为在定时器里面,this是window
                console.log(this.index, this.innerHTML);
            }.bind(this), 1000)
        }
    }
</script>
```

### 4.3.4、小结

- call 和 apply 特性一样
  - 都是用来调用函数，而且是立即调用
  - 但是可以在调用函数的同时，通过第一个参数指定函数内部 `this` 的指向
  - call 调用的时候，参数必须以参数列表的形式进行传递，也就是以逗号分隔的方式依次传递即可
  - apply 调用的时候，参数必须是一个数组，然后在执行的时候，会将数组内部的元素一个一个拿出来，与形参一一对应进行传递
  - 如果第一个参数指定了 `null` 或者 `undefined` 则内部 this 指向 window
- bind
  - 可以用来指定内部 this 的指向，然后生成一个改变了 this 指向的新的函数
  - 它和 call、apply 最大的区别是：bind 不会调用
  - bind 支持传递参数，它的传参方式比较特殊，一共有两个位置可以传递
    - 在 bind 的同时，以参数列表的形式进行传递
    - 在调用的时候，以参数列表的形式进行传递
    - 那到底以谁 bind 的时候传递的参数为准呢还是以调用的时候传递的参数为准
    - 两者合并：bind 的时候传递的参数和调用的时候传递的参数会合并到一起，传递到函数内部

## 4.4、函数的其它成员

- arguments
  - 实参集合
- caller
  - 函数的调用者
- length
  - 形参的个数
- name
  - 函数的名称

```js
function fn(x, y, z) {
  console.log(fn.length) // => 形参的个数
  console.log(arguments) // 伪数组实参参数集合
  console.log(arguments.callee === fn) // 函数本身
  console.log(fn.caller) // 函数的调用者
  console.log(fn.name) // => 函数的名字
}

function f() {
  fn(10, 20, 30)
}

f()
```

## 4.5、高阶函数

- 函数可以作为参数
- 函数可以作为返回值

**作为参数**

```javascript
function eat (callback) {
  setTimeout(function () {
    console.log('吃完了')
    callback()
  }, 1000)
}

eat(function () {
  console.log('去唱歌')
})
```

**作为返回值**

```javascript
function genFun (type) {
  return function (obj) {
    return Object.prototype.toString.call(obj) === type
  }
}

var isArray = genFun('[object Array]')
var isObject = genFun('[object Object]')

console.log(isArray([])) // => true
console.log(isArray({})) // => true
```

<a id="p6-5"></a>
# 八、附录

## 8.1、代码规范

### 8.1.1、代码风格

- [JavaScript Standard Style ](https://github.com/feross/standard)
- [Airbnb JavaScript Style Guide() {](https://github.com/airbnb/javascript)

### 8.1.2、校验工具

- [JSLint](https://github.com/douglascrockford/JSLint)
- [JSHint](https://github.com/jshint/jshint)
- [ESLint](https://github.com/eslint/eslint)

## 8.2、文档相关工具

- 电子文档制作工具: [docute](https://github.com/egoist/docute)
- 流程图工具：[DiagramDesigner](http://logicnet.dk/DiagramDesigner/)

