# ES6 教程（上、下汇总版）

> 本文档由「ES6 教程（上）」「ES6 教程（下）」合并而成，共 21 个章节。

## 目录

- [**一**、ECMASript 相关介绍](#一ecmasript-相关介绍)
- [二、let和const](#二let和const)
- [三、解构赋值](#三解构赋值)
- [四、模板字符串](#四模板字符串)
- [五、对象属性与方法简写](#五对象属性与方法简写)
- [六、箭头函数](#六箭头函数)
- [七、Array API](#七array-api)
- [八、函数参数默认值](#八函数参数默认值)
- [九、REST参数](#九rest参数)
- [十、spread 扩展运算符](#十spread-扩展运算符)
- [十一、Symbol](#十一symbol)
- [十二、迭代器](#十二迭代器)
- [十三、生成器](#十三生成器)
- [十四、Promise](#十四promise)
- [十五、Set集合](#十五set集合)
- [十六、Map集合](#十六map集合)
- [十七、面向对象](#十七面向对象)
- [十八、数值扩展](#十八数值扩展)
- [十九、对象方法扩展](#十九对象方法扩展)
- [二十、ES6模块化](#二十es6模块化)
- [二十一、环境兼容](#二十一环境兼容)

---

# **一**、ECMASript 相关介绍

## ECMA概述

![](images/微信截图_20201004101830.png)

​	Ecma国际（Ecma International）是一家国际性会员制度的信息和电信标准组织。1994年之前，名为欧洲计算机制造商协会（European Computer Manufacturers Association）。因为计算机的国际化，组织的标准牵涉到很多其他国家，因此组织决定改名表明其国际性。

​	这个组织的目标是评估、开发和认可电信和计算机标准。

​	该组织在1961年的日内瓦建立为了标准化欧洲的计算机系统。在欧洲制造、销售或开发计算机和电信系统的公司都可以申请成为会员。

## ECMAScript概述

​	ECMAScript 是由 Ecma 国际通过 ECMA-262 标准化的脚本程序设计语言。

​	Ecma 国际制定了许多标准，而 ECMA-262 只是其中的一个，所有标准列表查看http://www.ecma-international.org/publications/standards/Standard.htm

​	ECMAScript 6.0（以下简称 ES6）是 JavaScript 语言的下一代标准，已经在 2015 年 6 月正式发布了。它的目标，是使得 JavaScript 语言可以用来编写复杂的大型应用程序，成为企业级开发语言。

​	ES6不是新的技术体系，只是JavaScript的最新版本。

### ECMAScript 和 JavaScript 的关系

一个常见的问题是，ECMAScript 和 JavaScript 到底是什么关系？

要讲清楚这个问题，需要回顾历史。1996 年 11 月，JavaScript 的创造者 Netscape 公司，决定将 JavaScript 提交给标准化组织 ECMA，希望这种语言能够成为国际标准。次年，ECMA 发布 262 号标准文件（ECMA-262）的第一版，规定了浏览器脚本语言的标准，并将这种语言称为 ECMAScript，这个版本就是 1.0 版。

该标准从一开始就是针对 JavaScript 语言制定的，但是之所以不叫 JavaScript，有两个原因。一是商标，Java 是 Sun 公司的商标，根据授权协议，只有 Netscape 公司可以合法地使用 JavaScript 这个名字，且 JavaScript 本身也已经被 Netscape 公司注册为商标。二是想体现这门语言的制定者是 ECMA，不是 Netscape，这样有利于保证这门语言的开放性和中立性。

因此，ECMAScript 和 JavaScript 的关系是，前者是后者的规范，后者是前者的一种实现（另外的 ECMAScript 方言还有 JScript 和 ActionScript）。日常场合，这两个词是可以互换的。

### ES6 与 ECMAScript 2015 的关系

ECMAScript 2015（简称 ES2015）这个词，也是经常可以看到的。它与 ES6 是什么关系呢？

2011 年，ECMAScript 5.1 版发布后，就开始制定 6.0 版了。因此，ES6 这个词的原意，就是指 JavaScript 语言的下一个版本。

但是，因为这个版本引入的语法功能太多，而且制定过程当中，还有很多组织和个人不断提交新功能。事情很快就变得清楚了，不可能在一个版本里面包括所有将要引入的功能。常规的做法是先发布 6.0 版，过一段时间再发 6.1 版，然后是 6.2 版、6.3 版等等。

但是，标准的制定者不想这样做。他们想让标准的升级成为常规流程：任何人在任何时候，都可以向标准委员会提交新语法的提案，然后标准委员会每个月开一次会，评估这些提案是否可以接受，需要哪些改进。如果经过多次会议以后，一个提案足够成熟了，就可以正式进入标准了。这就是说，标准的版本升级成为了一个不断滚动的流程，每个月都会有变动。

标准委员会最终决定，标准在每年的 6 月份正式发布一次，作为当年的正式版本。接下来的时间，就在这个版本的基础上做改动，直到下一年的 6 月份，草案就自然变成了新一年的版本。这样一来，就不需要以前的版本号了，只要用年份标记就可以了。

ES6 的第一个版本，就这样在 2015 年 6 月发布了，正式名称就是《ECMAScript 2015 标准》（简称 ES2015）。2016 年 6 月，小幅修订的《ECMAScript 2016 标准》（简称 ES2016）如期发布，这个版本可以看作是 ES6.1 版，因为两者的差异非常小（只新增了数组实例的`includes`方法和指数运算符），基本上是同一个标准。根据计划，2017 年 6 月发布 ES2017 标准。

因此，ES6 既是一个历史名词，也是一个泛指，含义是 5.1 版以后的 JavaScript 的下一代标准，涵盖了 ES2015、ES2016、ES2017 等等，而 ES2015 则是正式名称，特指该年发布的正式版本的语言标准。本书中提到 ES6 的地方，一般是指 ES2015 标准，但有时也是泛指“下一代 JavaScript 语言”。

### 语法提案的批准流程

任何人都可以向标准委员会（又称 TC39 委员会）提案，要求修改语言标准。

一种新的语法从提案到变成正式标准，需要经历五个阶段。每个阶段的变动都需要由 TC39 委员会批准。

- Stage 0 - Strawman（展示阶段）
- Stage 1 - Proposal（征求意见阶段）
- Stage 2 - Draft（草案阶段）
- Stage 3 - Candidate（候选人阶段）
- Stage 4 - Finished（定案阶段）

一个提案只要能进入 Stage 2，就差不多肯定会包括在以后的正式标准里面。ECMAScript 当前的所有提案，可以在 TC39 的官方网站[GitHub.com/tc39/ecma262](https://github.com/tc39/ecma262)查看。

## ECMAScript 的历史

ECMA-262（ECMAScript）历史版本查看网址 

http://www.ecma-international.org/publications/standards/Ecma-262-arch.htm 

ES6 从开始制定到最后发布，整整用了 15 年。

前面提到，ECMAScript 1.0 是 1997 年发布的，接下来的两年，连续发布了 ECMAScript 2.0（1998 年 6 月）和 ECMAScript 3.0（1999 年 12 月）。3.0 版是一个巨大的成功，在业界得到广泛支持，成为通行标准，奠定了 JavaScript 语言的基本语法，以后的版本完全继承。直到今天，初学者一开始学习 JavaScript，其实就是在学 3.0 版的语法。

2000 年，ECMAScript 4.0 开始酝酿。这个版本最后没有通过，但是它的大部分内容被 ES6 继承了。因此，ES6 制定的起点其实是 2000 年。

为什么 ES4 没有通过呢？因为这个版本太激进了，对 ES3 做了彻底升级，导致标准委员会的一些成员不愿意接受。ECMA 的第 39 号技术专家委员会（Technical Committee 39，简称 TC39）负责制订 ECMAScript 标准，成员包括 Microsoft、Mozilla、Google 等大公司。

2007 年 10 月，ECMAScript 4.0 版草案发布，本来预计次年 8 月发布正式版本。但是，各方对于是否通过这个标准，发生了严重分歧。以 Yahoo、Microsoft、Google 为首的大公司，反对 JavaScript 的大幅升级，主张小幅改动；以 JavaScript 创造者 Brendan Eich 为首的 Mozilla 公司，则坚持当前的草案。

2008 年 7 月，由于对于下一个版本应该包括哪些功能，各方分歧太大，争论过于激烈，ECMA 开会决定，中止 ECMAScript 4.0 的开发，将其中涉及现有功能改善的一小部分，发布为 ECMAScript 3.1，而将其他激进的设想扩大范围，放入以后的版本，由于会议的气氛，该版本的项目代号起名为 Harmony（和谐）。会后不久，ECMAScript 3.1 就改名为 ECMAScript 5。

2009 年 12 月，ECMAScript 5.0 版正式发布。Harmony 项目则一分为二，一些较为可行的设想定名为 JavaScript.next 继续开发，后来演变成 ECMAScript 6；一些不是很成熟的设想，则被视为 JavaScript.next.next，在更远的将来再考虑推出。TC39 委员会的总体考虑是，ES5 与 ES3 基本保持兼容，较大的语法修正和新功能加入，将由 JavaScript.next 完成。当时，JavaScript.next 指的是 ES6，第六版发布以后，就指 ES7。TC39 的判断是，ES5 会在 2013 年的年中成为 JavaScript 开发的主流标准，并在此后五年中一直保持这个位置。

2011 年 6 月，ECMAScript 5.1 版发布，并且成为 ISO 国际标准（ISO/IEC 16262:2011）。

2013 年 3 月，ECMAScript 6 草案冻结，不再添加新功能。新的功能设想将被放到 ECMAScript 7。

2013 年 12 月，ECMAScript 6 草案发布。然后是 12 个月的讨论期，听取各方反馈。

2015 年 6 月，ECMAScript 6 正式通过，成为国际标准。从 2000 年算起，这时已经过去了 15 年。

目前，各大浏览器对 ES6 的支持可以查看[kangax.github.io/compat-table/es6/](https://kangax.github.io/compat-table/es6/)。

Node.js 是 JavaScript 的服务器运行环境（runtime）。它对 ES6 的支持度更高。除了那些默认打开的功能，还有一些语法功能已经实现了，但是默认没有打开。使用下面的命令，可以查看 Node.js 默认没有打开的 ES6 实验性语法。

```bash
// Linux & Mac
$ node --v8-options | grep harmony

// Windows
$ node --v8-options | findstr harmony
```

### 版本内容

| 版本        | 年份               | 内容变更                                                     |
| ----------- | ------------------ | ------------------------------------------------------------ |
| 第 1 版     | 1997 年            | 制定了语言的基本语法                                         |
| 第 2 版     | 1998 年            | 较小改动                                                     |
| 第 3 版     | 1999 年            | 引入正则、异常处理、格式化输出等。IE 开始支持                |
| 第 4 版     | 2007 年            | 过于激进，未发布                                             |
| 第 5 版     | 2009 年            | 引入严格模式、JSON，扩展对象、数组、原型、字符串、日期方法   |
| **第 6 版** | **2015 年**        | 模块化、面向对象语法、Promise、箭头函数、<br>let、const、数组解构赋值等等 |
| 第 7 版     | 2016 年            | 幂运算符、数组扩展、 Async/await 关键字                      |
| 第 8 版     | 2017 年            | Async/await、字符串扩展                                      |
| 第 9 版     | 2018 年            | 对象解构赋值、正则扩展                                       |
| 第 10 版    | 2019 年            | 扩展对象、数组方法                                           |
| ES.next     | 动态指向下一个版本 |                                                              |

**注：从 ES6 开始，每年发布一个版本，版本号比年份最后一位大 1**

## ECMA-262标准的维护

TC39（Technical Committee 39）是推进 ECMAScript 发展的委员会。其会员都是公司（其中主要是浏览器厂商，有苹果、谷歌、微软、因特尔等）。TC39 定期召开会议，会议由会员公司的代表与特邀专家出席。

## 为什么要学习 ES6 

​	目前，前端发展迅猛；JavaScript是前端发展的主要组成部分；ECMAScript标准目前已经发展到了ES11；ES最新版规范增加了很多新特性；

​	**这些新特性语法简洁、功能丰富、而且部分特性可以提升我们的网站性能；**新特性语法已经成为目前前端开发的重要技术，前端三大框架Vue、React、Angular都在使用大量的新特性语法，框架升级也在向新特性语法靠拢；

​	目前，各大招聘网站对于前端开发人员的要求，其中一个重要指标就是ES6；

​	⚫ ES6 的版本变动内容最多，具有里程碑意义 

​	⚫ ES6 加入许多新的语法特性，编程实现更简单、高效 

​	⚫ ES6 是前端发展趋势，就业必备技能 

## ES6 兼容性

http://kangax.github.io/compat-table/es6/ 可查看兼容性

![](images/微信截图_20201004104136.png)

# 二、let和const

## JavaScript作用域

### 什么是作用域

​	由于代码执行会形成代码执行的空间，这个执行空间指的就是我们的作用域。 表达式，函数执行的环境就会产生作用域，也就是变量和函数能作用到的范围，在这个范围内起作用，它就是所谓的作用域。 

```js
function outFun2() {
    var inVariable = "内层变量2";
}
outFun2();//要先执行这个函数，否则根本不知道里面是啥
console.log(inVariable); // Uncaught ReferenceError: inVariable is not defined
```

​	从上面的例子可以体会到作用域的概念，变量 inVariable 在全局作用域没有声明，所以在全局作用域下取值会报错。我们可以这样理解：**作用域就是一个独立的地盘，让变量不会外泄、暴露出去**。也就是说**作用域最大的用处就是隔离变量，不同作用域下同名变量不会有冲突。**

​	**ES6 之前 JavaScript 没有块级作用域,只有全局作用域和函数作用域**。ES6 的到来，为我们提供了‘**块级作用域**’,可通过新增命令 let 和 const 来体现。

### 全局作用域

函数之外声明的变量，会成为**全局变量**。

全局变量的作用域是**全局的**：网页的所有脚本和函数都能够访问它。

**一般来说以下几种情形拥有全局作用域:**

- 最外层函数和在最外层函数外面定义的变量拥有全局作用域

```js
var outVariable = "我是最外层变量"; //最外层变量
function outFun() { //最外层函数
    var inVariable = "内层变量";
    function innerFun() { //内层函数
        console.log(inVariable);
    }
    innerFun();
}
console.log(outVariable); //我是最外层变量
outFun(); //内层变量
console.log(inVariable); //inVariable is not defined
innerFun(); //innerFun is not defined
```

- 所有末定义直接赋值的变量自动声明为拥有全局作用域

```js
function outFun2() {
    variable = "未定义直接赋值的变量";
    var inVariable2 = "内层变量2";
}
outFun2();//要先执行这个函数，否则根本不知道里面是啥
console.log(variable); //未定义直接赋值的变量
console.log(inVariable2); //inVariable2 is not defined
```

- 所有 window 对象的属性拥有全局作用域

一般情况下，window 对象的内置属性都拥有全局作用域，例如 window.name、window.location、window.top 等等。

全局作用域有个弊端：如果我们写了很多行 JS 代码，变量定义都没有用函数包括，那么它们就全部都在全局作用域中。这样就会 污染全局命名空间, 容易引起命名冲突。

```js
// 张三写的代码中
var data = {a: 100}

// 李四写的代码中
var data = {x: true}
```

这就是为何 jQuery、Zepto 等库的源码，所有的代码都会放在`(function(){....})()`中。因为放在里面的所有变量，都不会被外泄和暴露，不会污染到外面，不会对其他的库或者 JS 脚本造成影响。这是函数作用域的一个体现。

### 函数作用域

**函数作用域： 由于函数执行，会产生作用域，这块作用域内存放着当前函数内部执行的代码中的变量，函数。**

```js
//在这里由于函数person执行，产生一块作用域里面包括name， getName 但是当person函数定义的时候就不会存里面内容，尽管这个函数体是这样的。
function person() { 
	var name = 'dxb' 
	function getName() { 
		console.log(name) 
	} 
} 
person();
alert(name); //错误
getName(); //错误
```

### 作用域链

通俗地讲，当声明一个函数时，局部作用域一级一级向上包起来，就是作用域链。

1.当执行函数时，总是先从函数内部找寻局部变量

2.如果内部找不到（函数的局部作用域没有），则会向创建函数的作用域（声明函数的作用域）寻找，依次向上

```js
var a = 1;

function fn() {
    var a = 10;

    function fn1() {
        var a = 20;
        console.log("fn1-->" + a); // 20
    }

    function fn2() {
        console.log("fn2-->" + a); // 10
    }
    fn1();
    fn2();
}

fn();
console.log("全局-->" + a); // 1
```

当执行fn1时，创建函数fn1的执行环境，并将该对象置于链表开头，然后将函数fn的调用对象放在第二位，最后是全局对象，作用域链的链表的结构是fn1->fn->window。从链表的开头寻找变量a，即fn1函数内部找变量a，找到了，结果是20。

同样，执行fn2时，作用域链的链表的结构是fn2->fn->window。从链表的开头寻找变量a，即fn2函数内部找变量a，找不到，于是从fn内部找变量a，找到了，结果是10。

最后在最外层打印出变量a，直接从变量a的作用域即全局作用域内寻找，结果为1。

## 块级作用域

### 为什么要有块级作用域

​	在过去 javascript的变量声明机制大家都已经接触过了，有什么呢，变量声明提升，函数声明整体提升。		

​	ECMAScript6新的语法可以更好的控制作用域。块级作用域的出现使得一系列的问题被解决。

**回顾var声明提升的机制，先看一段代码**

```js
if (false) {
    var a = 'wxb'
} else {
	console.log("a 的值为" + a)
}
/* 结果是什么呢？ a 的值为 undefined 没有报错， 没报错的前提是什么 a被定义 所以在这里的实质就是 */

/*
    var a ;// 在预编译阶段 变量进行的提升
    if(false) { 
        a = 'wxb' 
    } else { 
        console.log("a 的值为" + a) 
    }  
*/
// 接着在看一个例子 
var a = 'dxb';
// ......(此处省略10000行代码) 经过反复的思考觉得姓王也不错呢
var a = 'wxb' // 就把姓改了 姓王了 
console.log(a)
name = 'wxb' // 看到结果,喜闻乐见
```

值得注意的是：**块语句（大括号“｛｝”中间的语句），如 if 和 switch 条件语句或 for 和 while 循环语句，不像函数，它们不会创建一个新的作用域**。在块语句中定义的变量将保留在它们已经存在的作用域中。

1、存在作用域问题。

2、允许重复定义，污染同一作用域下的变量。

为了解决这个问题，引出块级作用域，使得作用域的变量可以更好的把控;

### 块级作用域

**块级作用域可通过新增命令 let 和 const 声明，所声明的变量在指定块的作用域外无法被访问**。块级作用域在如下情况被创建：

1. 在一个函数内部
2. 在一个代码块（由一对花括号包裹）内部

let 声明的语法与 var 的语法一致。你基本上可以用 let 来代替 var 进行变量声明，但会将变量的作用域限制在当前代码块中。

### let 关键字

let 关键字用来声明变量，使用 let 声明的变量有几个特点： 

- 不允许重复声明 
- 块级作用域 
- 不存在变量提升 
- 不影响作用域链 

**应用场景：以后声明变量使用 let 就对了**

```js
//声明变量
let a;
let b,c,d;
let e = 100;
let f = 521, g = 'iloveyou', h = [];

//1. 变量不能重复声明
// let star = '孙红雷';
// let star = '颜王';

//2. 块儿级作用域  全局, 函数, eval
// if else while for 
// {
//     let girl = '王骏迪';
// }
// console.log(girl);

//3. 不存在变量提升
// console.log(song);
// let song = '忠实的心儿想念你';

//4. 不影响作用域链
{
    let school = '新开普';
    function fn(){
        console.log(school);
    }
    fn();
}
```

#### let实例解析

```html
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>点击 DIV 换色</title>
    <link href="https://cdn.bootcss.com/twitter-bootstrap/3.3.7/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .item {
            width: 100px;
            height: 50px;
            border: solid 1px rgb(42, 156, 156);
            float: left;
            margin-right: 10px;
        }
    </style>
</head>

<body>
    <div class="container">
        <h2 class="page-header">点击切换颜色</h2>
        <div class="item"></div>
        <div class="item"></div>
        <div class="item"></div>
    </div>
    <script>
        //获取div元素对象
        let items = document.getElementsByClassName('item');

        //遍历并绑定事件
        for (let i = 0; i < items.length; i++) {
            items[i].onclick = function () {
                //修改当前元素的背景颜色
                // this.style.background = 'pink';
                items[i].style.background = 'pink';
            }
        }
        // 原理解析,如果是var,当事件回调函数触发的时候,i用的是3
        /* {
            var i = 0;
        }
        {
            var i = 1;
        }
        {
            var i = 2;
        }
        var i = 3;  */

        // 如果是let
        /* {
            var i = 0;
            items[i].onclick = function () {
                //修改当前元素的背景颜色
                // this.style.background = 'pink';
                items[i].style.background = 'pink';
            }
        }
        {
            let i = 1;
            items[i].onclick = function () {
                //修改当前元素的背景颜色
                // this.style.background = 'pink';
                items[i].style.background = 'pink';
            }
        }
        {
            let i = 2;
        } */
    </script>
</body>

</html>
```

### const 声明

const 关键字用来声明常量（不能修改的变量就是常量），const 声明有以下特点 

- 声明必须赋初始值 
- 标识符一般为大写 
- 不允许重复声明 
- 值不允许修改 
- 块级作用域 

注意: 对象属性修改和数组元素变化不会出发 const 错误 

**应用场景：声明对象类型使用 const，非对象类型声明选择 let**

```js
//声明常量
const SCHOOL = '新开普';

//1. 一定要赋初始值
// const A;

//2. 一般常量使用大写(潜规则)
// const a = 100;

//3. 常量的值不能修改
// SCHOOL = 'Newcapec'';

//4. 块儿级作用域
// {
//     const PLAYER = 'UZI';
// }
// console.log(PLAYER);

//5. 对于数组和对象的元素修改, 不算做对常量的修改, 不会报错
const TEAM = ['UZI', 'MLXG', 'Ming', 'Letme'];
// TEAM.push('XiaoHu');
```

**总结：**

- var：允许重复定义，污染同一作用域下的变量，没有块级作用域
- let：不允许重复定义，识别块级作用域
- const：不能重复定义，定义的是常量，识别块级作用域

## 闭包和递归

### 函数闭包

#### 闭包概念

**闭包函数：**声明在一个函数中的函数，叫做闭包函数。[不是说所有函数内部的函数都叫闭包函数,闭包函数绝对是函数内部的函数]

**闭包：**内部函数总是可以访问其所在的外部函数中声明的参数和变量，即使在其外部函数被返回（寿命终结）了之后。

```js
function outer() {
    var a = '变量1'
    var inner = function () {
    	console.info(a)
    }
	return inner // inner 就是一个闭包函数，因为他能够访问到outer函数的作用域
}
```

由于在 Javascript 语言中，只有函数内部的子函数才能读取局部变量，因此可以把闭包简单理解成 “定义在一个函数内部的函数”。

所以，在本质上，闭包就是将函数内部和函数外部连接起来的一座桥梁。

闭包的用途：

- 可以在函数外部读取函数内部成员
- 让函数内成员始终存活在内存中

很多人会搞不懂匿名函数与闭包的关系，实际上，闭包是站在作用域的角度上来定义的。因为inner访问到outer作用域的变量，所以inner就是一个闭包函数。虽然定义很简单，但是有很多坑点，比如this指向、变量的作用域，稍微不注意可能就造成内存泄露。

我们先把问题抛一边，思考一个问题：为什么闭包函数能够访问其他函数的作用域 ?

**从堆栈的角度看待js函数**

​	基本变量的值一般都是存在栈内存中，而对象类型的变量的值存储在堆内存中，栈内存存储对应空间地址。基本的数据类型: Number 、Boolean、Undefined、String、Null。

```js
var a = 1 //a是一个基本类型
var b = {m: 20 } //b是一个对象
```

**对应内存存储：**

![](images/微信截图_20201005101113.png)

当我们执行 b={m:30}时，堆内存就有新的对象{m：30}，栈内存的b指向新的空间地址( 指向{m：30} )，而堆内存中原来的{m：20}就会被程序引擎垃圾回收掉，节约内存空间。我们知道js函数也是对象，它也是在堆与栈内存中存储的，我们来看一下转化：

```js
var a = 1;
function fn(){
    var b = 2;
    function fn1(){
        console.log(b);
    }
    fn1();
}
fn();
```

![](images/微信截图_20201005101334.png)

栈是一种先进后出的数据结构：

1） 在执行fn前，此时我们在全局执行环境(浏览器就是window作用域)，全局作用域里有个变量a；

2） 进入fn，此时栈内存就会push一个fn的执行环境，这个环境里有变量b和函数对象fn1，这里可以访问自身执行环境和全局执行环境所定义的变量

3） 进入fn1，此时栈内存就会push 一个fn1的执行环境，这里面没有定义其他变量，但是我们可以访问到fn和全局执行环境里面的变量，因为程序在访问变量时，是向底层栈一个个找，如果找到全局执行环境里都没有对应变量，则程序抛出underfined的错误。

4） 随着fn1()执行完毕，fn1的执行环境被销毁，接着执行完fn()，fn的执行环境也会被销毁，只剩全局的执行环境下，现在没有b变量，和fn1函数对象了，只有a 和 fn(函数声明作用域是window下)

在函数内访问某个变量是根据函数作用域链来判断变量是否存在的，而函数作用域链是程序根据函数所在的执行环境栈来初始化的，所以上面的例子，我们在fn1里面打印变量b，根据fn1的作用域链的找到对应fn执行环境下的变量b。所以当程序在调用某个函数时，做了以下的工作：准备执行环境，初始函数作用域链和arguments参数对象.

我们现在看回最初的例子outer与inner

```js
function outer() {
     var  a = '变量1'
     var  inner = function () {
            console.info(a)
     }
    return inner    // inner 就是一个闭包函数，因为他能够访问到outer函数的作用域
}
var  inner = outer()   // 获得inner闭包函数
inner() //"变量1"
```

当程序执行完var inner = outer()，其实outer的执行环境并没有被销毁，因为他里面的变量a仍然被被inner的函数作用域链所引用，当程序执行完inner(), 这时候，inner和outer的执行环境才会被销毁调；《JavaScript高级编程》书中建议：由于闭包会携带包含它的函数的作用域，因为会比其他函数占用更多内容，过度使用闭包，会导致内存占用过多。

#### 闭包特点

- 让外部访问函数内部变量成为可能；
- 局部变量会常驻在内存中；
- 可以避免使用全局变量，防止全局变量污染；
- 会造成内存泄漏（有一块内存空间被长期占用，而不被释放）

#### 闭包的创建

闭包就是可以创建一个独立的环境，每个闭包里面的环境都是独立的，互不干扰。闭包会发生内存泄漏，**每次外部函数执行的时 候，外部函数的引用地址不同，都会重新创建一个新的地址。**但凡是当前活动对象中有被内部子集引用的数据，那么这个时候，这个数据不删除，保留一根指针给内部活动对象。

闭包内存泄漏为： 

​	key = value，key 被删除了 value 常驻内存中; 

​	局部变量闭包升级版（中间引用的变量） => 自由变量；

​	**自由变量：在 A 中作用域要用到的变量  x，并没有在 A 中声明，要到别的作用域中找到他，这个变量 x 就是自由变量。**

```js
var x = 20;
function A (b) {
    return x + b;
}

A(10);  // 30
```

上面的都是什么鬼，很多人看到这些话就是一脸懵······

接下来，我们先看例子，看完例子再回看上面的概念，会理解的更！透！彻！

#### 闭包的应用场景

结论：闭包找到的是同一地址中父级函数中对应变量最终的值

最终秘诀就这一句话，每个例子请自行带入这个结论！！！！！！！！！！！！！

 **例子1**

```js
function funA(){
    var a = 10;  // funA的活动对象之中;
    return function(){   //匿名函数的活动对象;
        alert(a);
    }
}
var b = funA();
b();  //10
```

**例子2**

```js
function outerFn() {
    var i = 0;

    function innerFn() {
        i++;
        console.log(i);
    }
    return innerFn;
}
//每次外部函数执行的时候,都会开辟一块内存空间,外部函数的地址不同，都会重新创建一个新的地址
var inner = outerFn();
inner();
inner();
inner();
var inner2 = outerFn();
inner2();
inner2();
inner2();
//1 2 3 1 2 3
```

**例子3**

```js
var i = 0;
function outerFn(){
    function innnerFn(){
        i++;
        console.log(i);
    }
    return innnerFn;
}
var inner1 = outerFn();
var inner2 = outerFn();
inner1();
inner2();
inner1();
inner2();     
//1 2 3 4
```

**例子4**

```js
function fn(){
    var a = 3;
    return function(){
        return  ++a;                                     
    }
}
console.log(fn()());  // 4
console.log(fn()());  // 4
```

**例子5**

```js
function outerFn(){
    var i = 0;
    function innnerFn(){
        i++;
        console.log(i);
    }
    return innnerFn;
}
var inner1 = outerFn();
var inner2 = outerFn();
inner1();
inner2();
inner1();
inner2();    //1 1 2 2
```

**例子6**

```js
(function() { 
    var m = 0; 
    function getM() { return m; } 
    function seta(val) { m = val; } 
    window.g = getM; 
    window.f = seta; 
})(); 
f(100);
console.info(g());   //100  闭包找到的是同一地址中父级函数中对应变量最终的值
```

**例子7**

```js
var lis = document.getElementsByTagName("li");
for(var i=0;i<lis.length;i++){
    (function(i){
        lis[i].onclick = function(){
            console.log(i);
        };
    })(i);       //事件处理函数中闭包的写法
} 
```

**例子8**

```js
function m1(){
    var x = 1;
    return function(){
        console.log(++x);
    }
}

m1()();   //2
m1()();   //2
m1()();   //2

var m2 = m1();
m2();   //2
m2();   //3
m2();   //4
```

**例子9**

```js
var  fn=(function(){
    var  i=10;
    function  fn(){
        console.log(++i);
    }
    return   fn;
})() 
fn();   //11
fn();   //12
```

**例子10**

```js
function love1(){
    var num = 223;
    var me1 = function() {
        console.log(num);
    }
    num++;
    return me1;
}
var loveme1 = love1();
loveme1();   //输出224
```

**例子11：大厂笔试题**

```js
function fun(n,o) {
    console.log(o);
    return {
        fun:function(m) {
            return fun(m,n);
        }
    };
}
var a = fun(0);  //undefined
a.fun(1);  //0  
a.fun(2);  //0  
a.fun(3);  //0  
var b = fun(0).fun(1).fun(2).fun(3);   //undefined  0  1  2
var c = fun(0).fun(1);  
c.fun(2);  
c.fun(3);  //undefined  0  1  1
```

**例子12：大厂笔试题**

```js
function fn() {
    var arr = [];
    for (var i = 0; i < 5; i++) {
        arr[i] = function () {
            return i;
        }
    }
    return arr;
}
var list = fn();
console.log(list);
for (var i = 0, len = list.length; i < len; i++) {
    console.log(list[i]());
} //5 5 5 5 5
```

**例子13：大厂笔试题**

```js
function fn() {
    var arr = [];
    for (var i = 0; i < 5; i++) {
        arr[i] = (function (i) {
            return function () {
                return i;
            };
        })(i);
    }
    return arr;
}
var list = fn();
for (var i = 0, len = list.length; i < len; i++) {
    console.log(list[i]());
} //0 1 2 3 4
```

### 函数递归

递归就是调用自身的一种编程技巧，在程序设计中应用广泛。递归函数就是函数对自身的调用，是循环运算的一种算法模式。

#### JS递归运算

递归必须由以下两部分组成。

- 递归调用的过程。
- 递归终止的条件。

在没有限制的情况下，递归运算会无终止地自身调用。因此，在递归运算中要结合 if 语句进行控制，只有在某个条件成立时才允许执行递归，否则不允许调用自身。

#### 递归应用场景

主要解决一些数学运算，如阶乘函数、幂函数和斐波那契数列。

**下面示例使用递归运算来设计阶乘函数。**  

```js
var factorial = function (num) {
    if (num <= 1) {
        return 1;
    } else {
        return num * factorial(num - 1);
    }
}
console.log(factorial(5));  //返回5的阶乘值为120
```

在这个过程中，利用分支结构把递归结束条件和递归运算分开。

**解析递归型数据结构**

很多数据结构都具有递归特性，如 DOM 文档树、多级目录结构、多级导航菜单、家族谱系结构等。对于这类数据结构，使用递归算法进行遍历比较合适。

下面使用递归运算计算指定节点内所包含的全部节点数。  

```js
function f(n) { //统计指定节点及其所有子节点的元素个数
    var l = 0; //初始化计数变量
    if (n.nodeType == 1) l++; //如果是元素节点，则计数
    var child = n.childNodes; //获取子节点集合
    for (var i = 0; i < child.length; i++) { //遍历所有子节点
        l += f(child[i]); //递归运算，统计当前节点下所有子节点数
    }
    return l; //返回节点数
}
window.onload = function () {
    console.log(f(document.body)); //返回2，即body和script两个节点
}
```

**适合使用递归法解决问题**

有些问题最适合采用递归的方法求解，如汉诺塔问题。

下面使用递归运算设计汉诺塔演示函数。参数说明：n 表示金片数；a、b、c 表示柱子，注意排列顺序。返回说明：当指定金片数，以及柱子名称，将输出整个移动的过程。  

```js
function f(n, a, b, c) {
    if (n == 1) { //当为一片时，直接移动
        document.write("移动 【盘子" + n + "】从【" + a + "柱】到【" + c + "柱】<br>");
    } else {
        f(n - 1, a, c, b); //调整参数顺序。让参数a移给b
        document.write("移动 【盘子" + n + "】从【" + a + "柱】到【" + c + "柱】<br>");
        f(n - 1, b, a, c); //调整顺序，让参数b移给c
    }
}
f(3, "A", "B", "C"); //调用汉诺塔函数
```

运行结果如下：

```html
移动【盘子1】从【A柱】到【C柱】
移动【盘子2】从【A柱】到【B柱】
移动【盘子1】从【C柱】到【B柱】
移动【盘子3】从【A柱】到【C柱】
移动【盘子1】从【B柱】到【A柱】
移动【盘子2】从【B柱】到【C柱】
移动【盘子1】从【A柱】到【C柱】
```

#### JS尾递归

尾递归是递归的一种优化算法，递归函数执行时会形成一个调用函数，当子一层的函数代码执行完成之后，父一层的函数才会销毁调用记录，这样就形成了调用栈，栈的叠加可能会产生内存溢出。而尾递归函数的每子一层函数不再需要使用父一层的函数执行完毕就会销毁栈记录，避免了内存溢出，节省了内存空间。

**示例**

下面是阶乘的一种普通线性递归运算。

```js
function f (n) {
    return (n == 1) ? 1 : n * f (n - 1);
}
console.log(f(5));  //120
```

使用尾递归算法后，则可以使用以下方法。

```js
function f (n, a) {
    return (n == 1) ? a : f (n - 1, a * n);
}
console.log(f(5, 1));  //120
```

当 n=5 时，线性递归的递归过程如下。

```js
f (5) = {5 * f(4)}
      = {5 * {4 * f(3) }}
      = {5 * {4 * {3 * f(2)}}}
      = {5 * {4 * {3 * {2 * f(1)}}}}
      = {5 * {4 * {3 * {2 *1}}}}
      = {5 * {4 * {3 *2}}}
      = {5 * {4 * 6}
      = {5 * 24}
      = 120
```

而尾递归的递归过程如下。

```js
f (5) = f (5, 1)
    = f (4, 5)
    = f (3, 20)
    = f (2, 60)
    = f (1, 120)
    = 120
```

很容易看出，普通递归比尾递归更加消耗资源，每次重复的过程调用都使得调用链条不断加长，系统不得不使用栈进行数据保存和恢复，而尾递归就不存在这样的问题，因为它的状态完全由变量 n 和 a 保存。

从理论上分析，尾递归也是递归的一种类型，不过其算法具有迭代算法的特征。上面的阶乘尾递归可以改写为下面的迭代循环。  

```js
var n = 5;
var w = 1;
for (var i = 1; i <= 5; i ++) {
    w = w * i;
}
console.log(w);
```

尾递归由于直接返回值，不需要保存临时变量，所以性能不会产生线性增加，同时 JavaScript 引擎会将尾递归形式优化成非递归形式。

#### JS递归与迭代的区别

递归与迭代都是循环的一种，简单比较如下：

- 在程序结构上，递归是重复调用函数自身实现循环，迭代是通过循环结构实现。
- 在结束方式上，递归当满足终止条件时会逐层返回再结束，迭代直接使用计数器结束循环。
- 在执行效率上，迭代的效率明显高于递归。因为递归需要占用大量系统资源，如果递归深度很大，系统资源可能会不够用。
- 在编程实现上，递归可以很方便的把数学公式转换为程序，易理解，易编程。迭代虽然效率高，不需要系统开销，但不容易理解，编写复杂问题时比较麻烦。

在实际应用中，能不用递归就不用递归，递归都可以用迭代来代替。

# 三、解构赋值

解构赋值是对赋值运算符的扩展。

它是一种针对数组或者对象进行**模式匹配**，然后对其中的变量进行赋值。

在代码书写上简洁且易读，语义更加清晰明了；也方便了复杂对象中数据字段获取。

**在解构中，有下面两部分参与：**

​	解构的源，解构赋值表达式的右边部分。

​	解构的目标，解构赋值表达式的左边部分。

简单来说: 等号 左边的,就是我们要赋值的变量； 等号右边的是我们要赋予的值

var a = 10;    a就是要赋值的变量;  10就是我们要赋予的值

## 数组的解构赋值

### 解构语法

ES6可以这样为给变量赋值

```javascript
let [a,b,c] = [1,2,3];//a = 1;b = 2;c = 3;
console.log(a)
console.log(b)
console.log(c)
```

只要等号两边的模式相同，左边的变量就会被赋予对应的值；

```javascript
//可嵌套
let [a, [[b], c]] = [1, [[2], 3]];// a = 1   b = 2   c = 3

//可忽略
let [a, , b] = [1, 2, 3]; //a = 1   b = 3

//不完全解构
let [a,b] = [1];//a = 1;b = undefined;只要解构不成功变量的值就为undefined;

//剩余运算符
let [a, ...b] = [1, 2, 3];//a = 1  b = [2, 3]
```

如果等号的右边不是数组就会报错

```javascript
let [a] = 1;//这个语句会报错，
```

### 解构允许设置默认值

```javascript
//当解构模式有匹配结果，且匹配结果是 undefined 时，会触发默认值作为返回结果。
let [a,b = 2] = [1,undefined];//a = 1;b = 2;
let [a,b = 2] = [1];//a = 1;b = 2;
let [a = 1] = [];//a = 1;

//a 与 b 匹配结果为 undefined ，触发默认值：a = 3; b = a =3
let [a = 3, b = a] = [];     // a = 3, b = 3

//a 正常解构赋值，匹配结果：a = 1，b 匹配结果 undefined ，触发默认值：b = a =1
let [a = 3, b = a] = [1];    // a = 1, b = 1

//a 与 b 正常解构赋值，匹配结果：a = 1，b = 2
let [a = 3, b = a] = [1, 2]; // a = 1, b = 2
```

> **注意：**
>  ES6 内部使用严格相等运算符（===），判断一个位置是否有值。所以，如果一个数组成员不严格等于undefined，默认值是不会生效的。

```javascript
let [a = 1] = [undefined];//a =1;
let [a = 1] = [null];//a = null;
```

如果默认值是一个表达式，那么这个表达式是**惰性求值**的，即只有在用到的时候，才会求值。

```javascript
function f() {
  console.log('aaa');
}
let [x = f()] = [1];//x=1;因为x能取到值，所以函数f根本不会执行。
```

## 对象的解构赋值

对象解构就更神奇了，尤其是当你需要从一个复杂的、深层嵌套的对象中取值时，其作用更加明显。重申一下，对象解构与数组解构用的是同样的规则（即在赋值运算符左侧创建一个 对象模式， 使它的变量位置与 = 右侧对象的值位置相匹配）。

**在对象解构中，你需要指明那些需要被提取值的属性名称，以及将要被赋值的变量名**。跟数组解构一样，我们需要在赋值运算符左边先创建一个对象模式来映射被解构的对象。

尽管在这种情况下，我们想要提取的是 对象属性的值 (如：我们从 { prop: value } 中提取 value)。相应地，我们的对象模式必须有一个变量，这个变量的位置要跟我们即将提取的属性值所在的位置一致。

解构可以用于数组和对象，对象的解构与数组有一个重要的不同。

> **数组的元素是按次序排列的，变量的取值由它的位置决定； 而对象的属性没有次序，变量必须与属性同名，才能取到正确的值**。

```javascript
let {a,b}={a:1,b:2};//a=1;b=2;
let {a,b}={b:3,a:4};//a=4;b=3;
let {c}={b:3,a:4};//undefined;因为没有与c对应的同名属性，导致取不到值，最终只能是undefined；
```

如果变量名与属性名不一致，必须写成下面这样；

```javascript
var { foo: baz } = { foo: 'aaa', bar: 'bbb' };
console.log(baz) // "aaa"

let obj = { first: 'hello', last: 'world' };
let { first: f, last: l } = obj;
console.log(f) // 'hello'
console.log(l) // 'world'
```

这实际上说明，对象的解构赋值其实是下面形式的简写;

```javascript
let { foo: foo, bar: bar } = { foo: "aaa", bar: "bbb" };
```

**也就是说，对象的解构赋值的内部机制，是先找到同名属性，然后再赋给对应的变量。真正被赋值的是后者，而不是前者。**

```javascript
let { foo: baz } = { foo: "aaa", bar: "bbb" };
console.log(baz) // "aaa"
console.log(foo) // error: foo is not defined
```

【注意】采用这种写法时，变量的声明和赋值是一体的。对于let和const来说，变量不能重新声明，所以一旦赋值的变量以前声明过，就会报错。

```javascript
let foo;
let {foo} = {foo: 1}; // error:Identifier 'foo' has already been declared
let baz;
let {bar: baz} = {bar: 1}; //  error:Identifier 'baz' has already been declared
```

上面代码中，解构赋值的变量都会重新声明，所以报错了。不过，**因为var命令允许重新声明，所以这个错误只会在使用let和const命令时出现。**如果没有第二个let命令，上面的代码就不会报错。

```javascript
let foo;
({foo} = {foo: 1}); // 成功
let baz;
({bar: baz} = {bar: 1}); // 成功
```

上面代码中，let命令下面一行的圆括号是必须的，否则会报错。因为解析器会将起首的大括号，理解成一个代码块，而不是赋值语句。

和数组一样，解构也可以用于嵌套结构的对象

```javascript
let obj = {
  p: [
    'Hello',
    { y: 'World' }
  ]
};
let { p: [x, { y }] } = obj;
x // "Hello"
y // "World"
//注意，这时p是模式，不是变量，因此不会被赋值
var node = {
  loc: {
    start: {
      line: 1,
      column: 5
    }
  }
};
var { loc: { start: { line }} } = node;
line // 1
loc  // error: loc is undefined
start // error: start is undefined
//只有line是变量，loc和start都是模式，不会被赋值
```

对象的解构也可以指定默认值

```javascript
var {x = 3} = {};
x // 3
var {x, y = 5} = {x: 1};
x // 1
y // 5
var {x:y = 3} = {};
y // 3
var {x:y = 3} = {x: 5};
y // 5
var { message: msg = 'Something went wrong' } = {};
msg // "Something went wrong"
```

默认值生效的条件是，对象的属性值严格等于undefined。如下：

```javascript
var {x = 3} = {x: undefined};
x // 3
var {x = 3} = {x: null};
x // null
//上面代码中，如果x属性等于null，就不严格相等于undefined，导致默认值不会生效。
```

如果解构失败，变量的值等于undefined

```javascript
let {foo} = {bar: 'baz'};
foo // undefined
let {foo: {bar}} = {baz: 'baz'};//报错
//等号左边对象的foo属性，对应一个子对象。该子对象的bar属性，解构时会报错。原因很简单，因为foo这时等于undefined，再取子属性就会报错。
```

由于数组本质是特殊的对象，因此可以对数组进行对象属性的解构。

```javascript
let arr = [1, 2, 3];
let {0 : first, [arr.length - 1] : last} = arr;
first // 1
last // 3
```

## 字符串的解构赋值

- 字符串等:在数组的解构中，解构的目标若为可遍历对象，皆可进行解构赋值。可遍历对象即实现 Iterator 接口的数据。

```javascript
const [a, b, c, d, e] = 'hello';
a // "h"
b // "e"
c // "l"
d // "l"
e // "o"
```

- 类似数组的对象都有一个length属性，因此还可以对这个属性解构赋值。

```javascript
let {length : len} = 'hello';
len // 5
```

## 数值和布尔值的解构赋值

解构赋值时，如果等号右边是数值和布尔值，则会先转为对象。

```javascript
let {toString: s} = 123;
s === Number.prototype.toString // true
let {toString: s} = true;
s === Boolean.prototype.toString // true
//上面代码中，数值和布尔值的包装对象都有toString属性，因此变量s都能取到值。
```

**解构赋值的规则是，只要等号右边的值不是对象或数组，就先将其转为对象。由于undefined和null无法转为对象，所以对它们进行解构赋值，都会报错。**

```javascript
let { prop: x } = undefined; // TypeError
let { prop: y } = null; // TypeError
```

## 函数参数的解构赋值

- 函数的参数也可以使用解构赋值。

```javascript
function add([x, y]){
  return x + y;
}
add([1, 2]); // 3
```

- 函数参数的解构也可以使用默认值。

```javascript
function move({x = 0, y = 0} = {}) {
  return [x, y];
}
move({x: 3, y: 8}); // [3, 8]
move({x: 3}); // [3, 0]
move({}); // [0, 0]
move(); // [0, 0]
```

上面代码中，函数move的参数是一个对象，通过对这个对象进行解构，得到变量x和y的值。如果解构失败，x和y等于默认值。

```javascript
function move({x, y} = { x: 0, y: 0 }) {
  return [x, y];
}
move({x: 3, y: 8}); // [3, 8]
move({x: 3}); // [3, undefined]
move({}); // [undefined, undefined]
move(); // [0, 0]
```

# 四、模板字符串

## 声明方式

ES6 引入新的声明字符串的方式 『``』，在ES6之前我们是通过 ''或 ""声明字符串 

```js
// 声明
let str = `我也是一个字符串哦!`;
console.log(str, typeof str);
```

**反引号**就是1左边的键。

## 模版字符串特性

模板字符串（template string）是增强版的字符串，用反引号（`）标识，特点： 

1) 字符串中可以出现换行符 

2) 可以使用 ${xxx} 形式输出变量 

```js
let str = `<ul>
    <li>沈腾</li>
    <li>玛丽</li>
    <li>魏翔</li>
    <li>艾伦</li>
    </ul>`;
//3. 变量拼接
let star = '王宁';
let result = `${star}在前几年离开了开心麻花`;
console.log(result);
```

## 数模转换

数模转换，即数据和模型对接工作，将JSON格式的数据绑定到页面里进行动态显示；

```html
<!DOCTYPE html>
<html>

<head>
    <meta charset="UTF-8">
    <title></title>
</head>

<body>
    <table border="1" width="400" align="center">
        <thead>
            <tr>
                <th>姓名</th>
                <th>年龄</th>
                <th>地址</th>
            </tr>
        </thead>
        <tbody id="tab"></tbody>
    </table>

    <script type="text/javascript">
        let jsondata = [{
            "name": "汤姆",
            "age": 25,
            "city": "杭州"
        }, {
            "name": "杰克",
            "age": 26,
            "city": "深圳"
        }]

        var html_str = '';
        jsondata.forEach(item => {
            console.log('元素==>', item);
            //es5
            //html_str += '<tr><td>'+ item.name +'</td><td>'+ item.age +'</td><td>'+ item.city +'</td></tr>';
            //es6
            html_str += `<tr>
                            <td>${item.name}</td>
                            <td>${item.age}</td>
                            <td>${item.city}</td>
                        </tr>`;
        });


        var htmlNode = document.getElementById("tab"); //id字符串
        //	var htmlNode=document.querySelector("#tab");//CSS选择器
        htmlNode.innerHTML = html_str;
    </script>
</body>

</html>
```

# 五、对象属性与方法简写

ES6中，对对象字面量进行了很多增强，属性初始化简写和方法的简写

简写有两条基本原则：

- 同名的属性可以省略不写
- 对象中的方法中的 : function 可以省略不写

## 对象字面量

在JavaScript中，对象字面量是创建对象的一种方式，形式如下：

```js
let name = '新开普';
let change = function () {
    console.log('我们可以改变你!!');
}
const school = {
    name: name,
    change: change,
    improve: function () {
        console.log("我们可以提高你的技能");
    }
}
```

在ES6之前，对象字面量的属性与方法必须用严格的**键值对**形式定义。而ES6提供了简化写法。

## 简写方式

### 属性简写

如果对象字面量的属性由外部变量引入，且键名与变量名相同，值不变，则可以只写键名。

```js
const school = {
    name,
    change
}
```

### 方法简写

对象字面量的方法可简写为`xxx(){}`的形式。

```js
const school = {
    name,
    change,
    improve() {
        console.log("我们可以提高你的技能");
    }
}
```

### 坑点

在MVVM框架中，引擎需识别某些关键属性的固定键名以正常运行，若使用自定名称的对象简化，会导致错误。

# 六、箭头函数

当我们查阅当前一些主流的前端框架API时，还会发现有大量的 `=>` 符号，这就是es6标准下的箭头函数

## 语法结构

### 无参数

没有参数的需要用在箭头前加上小括号

```javascript
//无参
var noParamEs5 = function(){
    console.log('noParamEs5...');
}
noParamEs5();

let noParamEs6 = ()=>{
    console.log('noParamEs6...');
}
noParamEs6();
```

### 有参数

- 一个参数，直接使用

```javascript
var oneParamEs5 = function(p){
    console.log('oneParamEs5==>',p);
}
oneParamEs5('hello');

let oneParamEs6 = (p) =>{
    console.log('oneParamEs6==>',p);
}
oneParamEs6('你好');
```

- 多个参数需要用到小括号，参数间逗号间隔，例如两个数字相加

```javascript
var multiParamEs5 = function(a,b){
    console.log('multiParamEs5==>',a+b);
}
multiParamEs5(2,3);

let multiParamEs6 = (a,b)=>{
    console.log('multiParamEs6==>',a+b);
}
multiParamEs6(4,5);
```

### 有返回值

- 返回普通的结果

```javascript
//有返回值
var hasReturnEs5 = function(a, b){
    a++;b--;
    return a*b;
}
console.log('hasReturnEs5==>',hasReturnEs5(3,3)); //8

let hasReturnEs6 = (a, b)=>{
    a++;b--;
    return a*b;
}
console.log('hasReturnEs6==>',hasReturnEs6(4,4)); //15
```

【注意】：当函数体里有多条语句时，需要用到大括号

- 返回对象时需要用小括号包起来，因为大括号被占用解释为代码块了

```javascript
let getObj = ()=>{
		return {
			name: "chris",
			age: 35
		}
	}
	console.log('getObj==>',getObj().name);)
}
```

## 语法特性

### this指向

在有关js的面试题中，this始终一个话题热门。学习完js的基础知识后，我们都知道this主要有两个用途：

- 作为构造函数里一个代词指向构造函数本身，当构造函数的方法被调用时，指向调用者
- 在事件触发时指向事件源对象

**this 是静态的. this 始终指向函数声明时所在作用域下的 this 的值**

```javascript
function getName() {
    console.log(this.name);
}
let getName2 = () => {
    console.log(this.name);
}

//设置 window 对象的 name 属性
window.name = '新开普';
const school = {
    name: "Newcapec"
}

//直接调用
getName();
getName2();

// call 方法调用
getName.call(school);
getName2.call(school);
```

### 箭头函数不能用new

不能作为构造实例化对象

```javascript
var Person=function(name,age){
    this.name=name;
    this.age=age;
}
var p=new Person("Sure",23);
console.log('ES5==>',p.name,p.age);

var Student=(name,age)=>{
    this.name=name;
    this.age=age;
}
var s=new Student("Sure",35);//报错
console.log('ES6==>',s.name,s.age);//报错

//总结：箭头函数不能用来写构造函数
```

### 不能使用arguments

```javascript
//ES5
function fn1(a,b){
	console.log(arguments)
}
fn1(10,20);
fn1();

var func = () => {
    console.log(arguments)
}
func() //报错
```

### 箭头函数的简写

```js
//1) 省略小括号, 当形参有且只有一个的时候
let add = n => {
    return n + n;
}
console.log(add(9));
//2) 省略花括号, 当代码体只有一条语句的时候, 此时 return 必须省略
// 而且语句的执行结果就是函数的返回值
let pow = n => n * n;

console.log(pow(8));
```

## 实战案例

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>箭头函数实践</title>
    <style>
        div {
            width: 200px;
            height: 200px;
            background: #58a;
        }
    </style>
</head>
<body>
    <div id="ad"></div>
    <script>
        //需求-1  点击 div 2s 后颜色变成『粉色』
        //获取元素
        let ad = document.getElementById('ad');
        //绑定事件
        ad.addEventListener("click", function(){
            //保存 this 的值
            // let _this = this;
            //定时器
            setTimeout(() => {
                //修改背景颜色 this
                // console.log(this);
                // _this.style.background = 'pink';
                this.style.background = 'pink';
            }, 2000);
        });

        //需求-2  从数组中返回偶数的元素
        const arr = [1,6,9,10,100,25];
        // const result = arr.filter(function(item){
        //     if(item % 2 === 0){
        //         return true;
        //     }else{
        //         return false;
        //     }
        // });
        
        const result = arr.filter(item => item % 2 === 0);

        console.log(result);

        // 箭头函数适合与 this 无关的回调. 定时器, 数组的方法回调
        // 箭头函数不适合与 this 有关的回调.  事件回调, 对象的方法

    </script>
</body>

</html>
```

# 七、Array API

注：这里的API有的是ES6新增的，有的是ES6之前的；

## every() 方法

### 定义和用法

every() 方法用于检测数组所有元素是否都符合指定条件（通过函数提供）。

every() 方法使用指定函数检测数组中的所有元素：

- 如果数组中检测到有一个元素不满足，则整个表达式返回 *false* ，且剩余的元素不会再进行检测。
- 如果所有元素都满足条件，则返回 true。

**注意：** every() 不会对空数组进行检测。

**注意：** every() 不会改变原始数组。

### 语法

```js
array.every(function(currentValue,index,arr), thisValue)
```

### 参数说明

| 参数                                | 描述                                                         |
| ----------------------------------- | ------------------------------------------------------------ |
| *function(currentValue, index,arr)* | 必须。函数，数组中的每个元素都会执行这个函数 <br>函数参数: <br/>currentValue    必须。当前元素的值<br/>*index*可选。当前元素的索引值<br/>*arr*可选。当前元素属于的数组对象 |
| *thisValue*                         | 可选。对象作为该执行回调时使用，传递给函数，用作 "this" 的值。 如果省略了 thisValue ，"this" 的值为 "undefined" |

### 案例

```html
<p>点击按钮检测数组的所有元素是否都大于 18 :</p>
<button onclick="myFunction()">点我</button>
<p id="demo"></p>
<script>
var ages = [32, 33, 16, 40];
function checkAdult(age) {
    return age >= 18;
}
function myFunction() {
    document.getElementById("demo").innerHTML = ages.every(checkAdult);
}
</script>
```

## some() 方法

### 定义和用法

some() 方法用于检测数组中的元素是否满足指定条件（函数提供）。

some() 方法会依次执行数组的每个元素：

- 如果有一个元素满足条件，则表达式返回*true* , 剩余的元素不会再执行检测。
- 如果没有满足条件的元素，则返回false。

**注意：** some() 不会对空数组进行检测。

**注意：** some() 不会改变原始数组。

### 语法

```js
array.some(function(currentValue,index,arr),thisValue)
```

### 参数说明

同every();

### 案例

```js
// 检测数组中是否有元素大于 18:
var ages = [3, 10, 18, 20];

function checkAdult(age) {
    return age >= 18;
}

var tf = ages.some(checkAdult);
```

## fill() 方法

### 定义和用法

fill() 方法用于将一个固定值替换数组的元素。

### 语法

```js
array.fill(value, start, end)
```

### 参数

| 参数    | 描述                                       |
| ------- | ------------------------------------------ |
| *value* | 必需。填充的值。                           |
| *start* | 可选。开始填充位置。                       |
| *end*   | 可选。停止填充位置 (默认为 *array*.length) |

### 案例

```js
// 使用固定值填充数组：
var fruits = ["Banana", "Orange", "Apple", "Mango"];
fruits.fill("Newcapec");

// 填充 "Newcapec" 到数组的最后两个元素：
var fruits = ["Banana", "Orange", "Apple", "Mango"];
fruits.fill("Newcapec", 2, 4);
```

## filter() 方法

### 定义和用法

filter() 方法创建一个新的数组，新数组中的元素是通过检查指定数组中符合条件的所有元素。

**注意：** filter() 不会对空数组进行检测。

**注意：** filter() 不会改变原始数组。

### 语法

```js
array.filter(function(currentValue,index,arr), thisValue)
```

### 参数说明

同every();

### 案例

```js
// 返回数组 ages 中所有元素都大于 18 的元素:
var ages = [32, 33, 16, 40];

function checkAdult(age) {
    return age >= 18;
}

var filterAge = ages.filter(checkAdult);
console.log(filterAge)
// 32,33,40
```

## forEach() 方法

### 定义和用法

forEach() 方法用于调用数组的每个元素，并将元素传递给回调函数。

**注意:** forEach() 对于空数组是不会执行回调函数的。

### 语法

```js
array.forEach(function(currentValue, index, arr), thisValue)
```

### 参数

同every();

### 案例

```js
//最早之前我们是这边遍历数组的
var array = [1, 2, 3, 4];

for(var k = 0; k < array.length; k++) {
	alert(array[k]);
}

//ES5我们可以这样
for(var k in array) {
    alert(array[k]);
}

//ES5 forEach 用法：Array在ES5新增的方法中，参数都是function类型，默认有传参
array.forEach(alert);

array.forEach(console.log);

// 结果：
// 1, 0, [1, 2, 3, 4]
// 2, 1, [1, 2, 3, 4]
// 3, 2, [1, 2, 3, 4]
// 4, 3, [1, 2, 3, 4]
//显而易见，forEach方法中的function回调支持3个参数，第1个是遍历的数组内容；第2个是对应的数组索引，第3个是数组本身。
[].forEach(function(value, index, array) {
    // ...
});

array.forEach(function(value,index,array){
    console.log(value)
});

//数组求和
var sum=0;
array.forEach(function(item, index, array) {
    console.log(item)
    sum += item;
});
alert(sum); // 10

//简化
var array = [1, 2, 3, 4];
var sum=0;
array.forEach(item=>{
    sum += item;
});
alert(sum); // 10
```

## map() 方法

### 定义和用法

map() 方法返回一个新数组，数组中的元素为原始数组元素调用函数处理后的值。

map() 方法按照原始数组元素顺序依次处理元素。

**注意：** map() 不会对空数组进行检测。

**注意：** map() 不会改变原始数组。

### 语法

```js
array.map(function(currentValue,index,arr), thisValue)
```

### 参数说明

同every();

### 案例

```js
// 返回一个数组，数组中元素为原始数组的平方根:
var numbers = [4, 9, 16, 25];

var newNums = numbers.map(Math.sqrt);
console.log(newNums)
// 2,3,4,5

var numbers = [4, 9, 16, 25];

var newNums = numbers.map(function (e) {
    return e * e;
});
console.log(newNums)
```

# 八、函数参数默认值

## 语法和用途

js的弱类型特点，在使用时非常方便，但也带来了一些负面作用。

比如一些值在参与运算时，可能会自动转换为false，这些值有：0，null，undefined，“”，NaN

举例说明：

```javascript
function add(a, b, c) {
    return a + b + c;
}

let r1 = add(1, 2, 3); // 6
let r2 = add(1, 2); // NaN
console.log(r1, r2);
```

但是ES6允许为函数的参数设置默认值，即直接写在参数定义的后面。

```javascript
// ES6 允许给函数参数赋值初始值
// 形参初始值 具有默认值的参数, 一般位置要靠后(潜规则)
function add(a, b, c = 10) {
    return a + b + c;
}
let result = add(1, 2);
console.log(result);
```

这种用法非常有用：

> 阅读代码的人，可以立刻意识到哪些参数是可以省略的，不用查看函数体或文档；
> 有利于将来的代码优化，即使未来的版本在对外接口中，彻底拿掉这个参数，也不会导致以前的代码无法运行。

## 参数的位置

```js
function fun1(x=1,y){
	return [x,y];
}

console.log('fun1==>',fun1());//[1,undefined]
console.log('fun1==>',fun1(2));//[2,undefined]
//console.log('fun1==>',f1(,2));//报错
console.log('fun1==>',fun1(undefined,2));//1,2


function fun2(x,y=10,z){
	return [x,y,z];
}
console.log('fun2==>',fun2());//[undefined,10,undefined]
console.log('fun2==>',fun2(1));//[1,10,undefined]
//console.log('fun2==>',f2(1,,2));//报错
console.log('fun2==>',fun2(1,undefined,2));//[1,10,2]

//默认值位置使用时注意事项，传入参数有不同的用法
```

## 与解构赋值结合

```js
function connect({
    host = "127.0.0.1",
    username,
    password,
    port
}) {
    console.log(host)
    console.log(username)
    console.log(password)
    console.log(port)
}
connect({
    host: 'newcapec.com',
    username: 'root',
    password: 'root',
    port: 3306
})
```

## 使用默认参数的注意事项

1. 形参不能在函数内部再使用let或const声明，否则会报错

```javascript
function fn(x=5){
    let x=1; //报错
    const x=2; //报错
}
```

2. 不能有同名形参，否则会报错

```javascript
functiong fn（a，b=1，b）{} // 报错
```

3. null用作实参时，会被直接传递，而undefined会被触发默认

```javascript
//null用作实参时，会被直接传递，而undefined会被触发默认
function foo(a,b=5){
	console.log(a,b);
}
foo(10,null);//10,null
foo(10,undefined);//10,5
```

# 九、REST参数

ES6 引入 rest 参数，用于获取函数的实参，用来代替 arguments

```js
// ES5 获取实参的方式
function data() {
    console.log(arguments);
}
data('小黑', '小红', '小明');
```

## rest参数用法

```js
/**
* 作用与 arguments 类似
*/
function add(...args){
 console.log(args);
}
add(1,2,3,4,5);
/**
* rest 参数必须是最后一个形参
*/
function minus(a,b,...args){
 console.log(a,b,args);
}
minus(100,1,2,3,4,5,19);
```

**注意：rest 参数非常适合不定个数参数函数的场景**
---

# 十、spread 扩展运算符

## 初始扩展运算符

​	扩展运算符（spread）也是三个点（...）。它好比 rest 参数的逆运算，将一个数组转为用逗号分隔的参数序列，对数组进行解包。

```js
// 『...』 扩展运算符能将『数组』转换为逗号分隔的『参数序列』
//声明一个数组 ...
const tfboys = ['易烊千玺', '王源', '王俊凯'];
// => '易烊千玺','王源','王俊凯'

// 声明一个函数
function spring() {
    console.log(arguments);
}

spring(...tfboys); // spring('易烊千玺','王源','王俊凯')
```

## 扩展运算符应用

```js
//1. 数组的合并 情圣  误杀  唐探
const chopsticks = ['王太利', '肖央'];
const phoenix = ['曾毅', '玲花'];
// const newGroup = chopsticks.concat(phoenix);
const newGroup = [...chopsticks, ...phoenix];
console.log(newGroup);

//2. 数组的克隆
const lol = ['EDG', 'RNG', 'JDG', 'TES'];
const copyLol = [...lol]; //  ['EDG', 'RNG', 'JDG', 'TES']
console.log(copyLol);

//3. 将伪数组转为真正的数组
const divs = document.querySelectorAll('div');
const divArr = [...divs];
console.log(divArr); // arguments
```

# 十一、Symbol

## Symbol 概述

​	ES5 的对象属性名都是字符串，这容易造成属性名的冲突。比如，你使用了一个他人提供的对象，但又想为这个对象添加新的方法（mixin 模式），新方法的名字就有可能与现有方法产生冲突。如果有一种机制，保证每个属性的名字都是独一无二的就好了，这样就从根本上防止属性名的冲突。这就是 ES6 引入`Symbol`的原因。

ES6 引入了一种新的原始数据类型`Symbol`，表示独一无二的值。它是 JavaScript 语言的第七种数据类型，前六种是：`undefined`、`null`、布尔值（Boolean）、字符串（String）、数值（Number）、对象（Object）。

Symbol 值通过`Symbol`函数生成。这就是说，对象的属性名现在可以有两种类型，一种是原来就有的字符串，另一种就是新增的 Symbol 类型。凡是属性名属于 Symbol 类型，就都是独一无二的，可以保证不会与其他属性名产生冲突。

**Symbol 特点** 

- Symbol 的值是唯一的，用来解决命名冲突的问题 
- Symbol 值不能与其他数据进行运算 
- Symbol 定义 的 对象属 性不能使用 for…in 循环遍历 ，但是可以使用Reflect.ownKeys 来获取对象的所有键名

```js
//创建Symbol
let s = Symbol();
console.log(s, typeof s);

// 创建带标识Symbol
let s2 = Symbol('新开普');
let s3 = Symbol('新开普');
console.log(s2 === s3);

//Symbol.for 创建
let s4 = Symbol.for('新开普');
let s5 = Symbol.for('新开普');
console.log(s4 === s5);

//不能与其他数据进行运算
//    let result = s + 100;
//    let result = s > 100;
let result = s + s;
```

## Symbol创建对象属性

```js
//向对象中添加方法 和up down相关的方法
let game = {
    name: '俄罗斯方块',
    up: function () {},
    down: function () {}
};

// 而且我们还要保证不能破坏对象的原有结构;【如果game对象结构简单,我们会很快发现是否存在up和down;但是如果结构复杂呢】
// 声明一个对象
let methods = {
    up: Symbol(),
    down: Symbol()
};

game[methods.up] = function () {
    console.log("我可以改变形状");
}

game[methods.down] = function () {
    console.log("我可以快速下降!!");
}

console.log(game);
// 调用
game[methods.up]();

//
let youxi = {
    name: "狼人杀",
    [Symbol('say')]: function () {
        console.log("我可以发言")
    },
    [Symbol('zibao')]: function () {
        console.log('我可以自爆');
    }
}

console.log(youxi)
// 调用
// Reflect.ownKeys(youxi)和Object.getOwnPropertySymbols(youxi)
var keys = Reflect.ownKeys(youxi);
console.log(keys)
youxi[keys[1]]();
```

注: 遇到唯一性的场景时要想到 Symbol

## Symbol内置属性

​	除了定义自己使用的 Symbol 值以外，ES6 还提供了 11 个内置的 Symbol 值，指向语言内部使用的方法。可以称这些方法为魔术方法，因为它们会在特定的场景下自动执行。 

​	这些内置属性，必须作为对象的属性存在；

| 属性                      | 作用                                                         |
| ------------------------- | ------------------------------------------------------------ |
| Symbol.hasInstance        | 当其他对象使用 instanceof 运算符，判断是否为该对象的实例时，会调用这个方法 |
| Symbol.isConcatSpreadable | 对象的 Symbol.isConcatSpreadable 属性等于的是一个布尔值，表示该对象用于 Array.prototype.concat()时，是否可以展开。 |
| Symbol.species            | 创建衍生对象时，会使用该属性                                 |
| Symbol.match              | 当执行 str.match(myObject) 时，如果该属性存在，会调用它，返回该方法的返回值。 |
| Symbol.replace            | 当该对象被 str.replace(myObject)方法调用时，会返回该方法的返回值。 |
| Symbol.search             | 当该对象被 str.search (myObject)方法调用时，会返回该方法的返回值。 |
| Symbol.split              | 当该对象被 str.split(myObject)方法调用时，会返回该方法的返回值。 |
| Symbol.iterator           | 对象进行 for...of 循环时，会调用 Symbol.iterator 方法，返回该对象的默认遍历器 |
| Symbol.toPrimitive        | 该对象被转为原始类型的值时，会调用这个方法，返回该对象对应的原始类型值。 |
| Symbol. toStringTag       | 在该对象上面调用 toString 方法时，返回该方法的返 回值        |
| Symbol. unscopables       | 该对象指定了使用 with 关键字时，哪些属性会被 with环境排除。  |

**实例代码：**

```js
class Person {
    static[Symbol.hasInstance](param) {
        console.log(param);
        console.log("我被用来检测类型了");
        return false;
    }
}

let o = {};

console.log(o instanceof Person);

const arr = [1, 2, 3];
const arr2 = [4, 5, 6];
arr2[Symbol.isConcatSpreadable] = false;
console.log(arr.concat(arr2));
```

## 举例理解

ES 6 引入了一个新的数据类型 Symbol，它是用来做什么的呢？

为了说明 Symbol 的作用，我们先来描述一个使用场景。

我们在做一个游戏程序，用户需要选择角色的种族。

```js
var race = {
  protoss: 'protoss', // 神族
  terran: 'terran', // 人族
  zerg: 'zerg' // 虫族
}

function createRole(type){
  if(type === race.protoss){创建神族角色}
  else if(type === race.terran){创建人族角色}
  else if(type === race.zerg){创建虫族角色}
}
```

那么用户选择种族后，就需要调用 createRole 来创建角色：

```js
// 传入字符串
createRole('zerg') 
// 或者传入变量
createRole(race.zerg)
```

一般传入字符串被认为是不好的做法，所以使用 createRole(race.zerg) 的更多。

如果使用 createRole(race.zerg)，那么聪明的读者会发现一个问题：race.protoss、race.terran、race.zerg 的值为多少并不重要。

改为如下写法，对 createRole(race.zerg) 毫无影响：

```js
var race = {
  protoss: 'askdjaslkfjas;lfkjas;flkj', // 神族
  terran: ';lkfalksjfl;askjfsfal;skfj', // 人族
  zerg: 'qwieqwoirqwoiruoiwqoisrqwroiu' // 虫族
}
```

也就是说：

**race.zerg 的值是多少无所谓，只要它的值跟 race.protoss 和 race.terran 的值不一样就行。**

Symbol 的用途就是如此：Symbol 可以创建一个独一无二的值（但并不是字符串）。

用 Symbol 来改写上面的 race：

```js
var race = {
  protoss: Symbol(),
  terran: Symbol(),
  zerg: Symbol()
}

race.protoss !== race.terran // true
race.protoss !== race.zerg // true
```

你也可以给每个 Symbol 起一个名字：

```js
var race = {
  protoss: Symbol('protoss'),
  terran: Symbol('terran'),
  zerg: Symbol('zerg')
}
```

不过这个名字跟 Symbol 的值并没有关系，你可以认为这个名字就是个注释。如下代码可以证明 Symbol 的名字与值无关：

```js
var a1 = Symbol('a')
var a2 = Symbol('a')
a1 !== a2 // true
```

如果你觉得我说得还是太复杂了，看不懂，你可以记一句话：

Symbol 生成一个全局唯一的值。

# 十二、迭代器

## 迭代器概述

​	遍历器（Iterator）就是一种机制。它是一种接口，为各种不同的数据结构提供统一的访问机制。任何数据结构只要部署 Iterator 接口，就可以完成遍历操作。

1) ES6 创造了一种新的遍历命令 for...of 循环，Iterator 接口主要供 for...of 消费 

2) 原生具备 iterator 接口的数据(可用 for of 遍历)

​	a) Array 

​	b) Arguments 

​	c) Set 

​	d) Map 

​	e) String 

​	f) TypedArray 

​	g) NodeList 

3) 工作原理

​	a) 创建一个指针对象，指向当前数据结构的起始位置 

​	b) 第一次调用对象的 next 方法，指针自动指向数据结构的第一个成员 

​	c) 接下来不断调用 next 方法，指针一直往后移动，直到指向最后一个成员 

​	d) 每调用 next 方法返回一个包含 value 和 done 属性的对象 

**注: 需要自定义遍历数据的时候，要想到迭代器。**

## 迭代器案例

### 遍历数组

```js
// 声明一个数组
const xiyou = ['唐僧', '孙悟空', '猪八戒', '沙僧'];
console.log(xiyou);

// 使用for in遍历数组
for (let v in xiyou) {
    // console.log(v);
    console.log(xiyou[v]);
}

// 使用 for...of 遍历数组
for (let v of xiyou) {
    console.log(v);
}

let iterator = xiyou[Symbol.iterator]();

//调用对象的next方法
console.log(iterator.next());
console.log(iterator.next());
console.log(iterator.next());
console.log(iterator.next());
console.log(iterator.next());
```

### 自定义遍历对象

```js
//声明一个对象
const banji = {
    name: "LOL学院",
    stus: [
        'Ming',
        'Ning',
        'Tian',
        'Knight',
        'Uzi'
    ],
    [Symbol.iterator]() {
        //索引变量
        let index = 0;
        let _this = this;
        return {
            next: function () {
                if (index < _this.stus.length) {
                    const result = {
                        value: _this.stus[index],
                        done: false
                    };
                    //下标自增
                    index++;
                    //返回结果
                    return result;
                } else {
                    return {
                        value: undefined,
                        done: true
                    };
                }
            }
        };
    }
}

//遍历这个对象 
for (let v of banji) {
    console.log(v);
}
```

# 十三、生成器

## 生成器概述

​	生成器函数是 ES6 提供的一种异步编程解决方案，语法行为与传统函数完全不同

```js
// 生成器其实就是一个特殊的函数
// 异步编程  纯回调函数  node fs  ajax mongodb
// 函数代码的分隔符
function* gen() {
    // console.log(111);
    yield '一只没有耳朵';
    // console.log(222);
    yield '一只没有尾部';
    // console.log(333);
    yield '真奇怪';
    // console.log(444);
}

let iterator = gen();
// iterator.next();
// iterator.next();
// iterator.next();
// iterator.next();
console.log(iterator.next());
console.log(iterator.next());
console.log(iterator.next());
console.log(iterator.next());

//遍历
// for(let v of gen()){
//     console.log(v);
// }
```

代码说明： 

​	1) * 的位置没有限制 

​	2) 生成器函数返回的结果是迭代器对象，调用迭代器对象的 next 方法可以得到 yield 语句后的值 

​	3) yield 相当于函数的暂停标记，也可以认为是函数的分隔符，每调用一次 next 方法，执行一段代码 

​	4) next 方法可以传递实参，作为 yield 语句的返回值

## 生成器函数参数

```js
function* gen(arg) {
    console.log(arg);
    let one = yield 111;
    console.log(one);
    let two = yield 222;
    console.log(two);
    let three = yield 333;
    console.log(three);
}

//执行获取迭代器对象
let iterator = gen('AAA');
console.log(iterator.next());
//next方法可以传入实参
console.log(iterator.next('BBB'));
console.log(iterator.next('CCC'));
console.log(iterator.next('DDD'));
```

## 生成器函数应用

### 案例一：解决回调地狱

```js
// 异步编程  文件操作 网络操作(ajax, request) 数据库操作
// 1s 后控制台输出 111  2s后输出 222  3s后输出 333 
// 回调地狱
// setTimeout(() => {
//     console.log(111);
//     setTimeout(() => {
//         console.log(222);
//         setTimeout(() => {
//             console.log(333);
//         }, 3000);
//     }, 2000);
// }, 1000);

function one(){
    setTimeout(()=>{
        console.log(111);
        iterator.next();
    },1000)
}

function two(){
    setTimeout(()=>{
        console.log(222);
        iterator.next();
    },2000)
}

function three(){
    setTimeout(()=>{
        console.log(333);
        iterator.next();
    },3000)
}

function * gen(){
    yield one();
    yield two();
    yield three();
}

//调用生成器函数
let iterator = gen();
iterator.next();
```

### 案例二

```js
//模拟获取  用户数据  订单数据  商品数据 
function getUsers() {
    setTimeout(() => {
        let data = '用户数据';
        //调用 next 方法, 并且将数据传入
        iterator.next(data);
    }, 1000);
}

function getOrders() {
    setTimeout(() => {
        let data = '订单数据';
        iterator.next(data);
    }, 1000)
}

function getGoods() {
    setTimeout(() => {
        let data = '商品数据';
        iterator.next(data);
    }, 1000)
}

function* gen() {
    let users = yield getUsers();
    console.log(users);
    let orders = yield getOrders();
    console.log(orders);
    let goods = yield getGoods();
    console.log(goods)
}

//调用生成器函数
let iterator = gen();
iterator.next();
```
# 十四、Promise

## Promise概述

​	Promise 是 ES6 引入的异步编程的新解决方案。语法上 Promise 是一个构造函数，用来封装异步操作并可以获取其成功或失败的结果。

​	Promise 对象用于一个异步操作的最终完成（或失败）及其结果值的表示。简单点说，它就是用于处理异步操作的，异步处理成功了就执行成功的操作，异步处理失败了就捕获错误或者停止后续操作。

​	直接在控制台输出查看结果，输出console.dir(Promise)，发现它就是一个构造函数，查看prototype属性，里面有catch和then，那些就是它的方法

![](images/es6-img03.png)

## Promise基本语法

实例化 Promise 对象

```javascript
var promise = new Promise(function (resolve, reject) {
    // 1、封装异步操作,使用setTimeout模拟异步操作
    setTimeout(() => {
        // 2、获取成功或失败的结果
        // 异步操作成功,那么就使用resolve(成功结果)
        // resolve("执行成功");
        /* resolve({
                    name: "张三",
                    age: 12
                }); */
        // 异步操作失败,那么就使用reject(失败结果)
        reject("数据获取失败");
    }, 2000);
});

// 通过promise的then(),then()可以根据promise的状态指向不同的回调
// then()可以传递两个回调,第一个是成功的回调,第二个是失败的回调
// 回调函数里面定义的形参,就是resolve和reject响应出来的数据
// 成功回调的形参一般命名为：value/data; 失败回调的形参一般命名为:reason
promise.then(function (value) {
    console.log(value)
}, function (reason) {
    console.error(reason)
})
```

执行上面的操作后，2秒以后控制台会有输出结果：“执行完成/用户数据”。

在Promise中的参数是一个执行器函数`executor`，它有两个参数`resolve`和`reject`。它内部通常有一些异步操作，如果异步操作成功，则可以调用resolve()来将该实例的状态置为`fulfilled`，即已完成的，如果一旦失败，可以调用reject()来将该实例的状态置为`rejected`，即失败的。

如果用自己的理解，来实现这样一个函数，应该是这样的：

```javascript
function runAsync(callback){
    setTimeout(function(){
        console.log('执行完成');
        callback('测试数据');
    }, 2000);
}

runAsync(function(data){
    console.log(data);
});
```

## Promise基本应用

### 封装读取文件

```js
//1. 引入 fs 模块
const fs = require('fs');

//2. 调用方法读取文件
// fs.readFile('./resources/为学.md', (err, data)=>{
//     //如果失败, 则抛出错误
//     if(err) throw err;
//     //如果没有出错, 则输出内容
//     console.log(data.toString());
// });

//3. 使用 Promise 封装
const p = new Promise(function (resolve, reject) {
    fs.readFile("./resources/为学.md", (err, data) => {
        //判断如果失败
        if (err) reject(err);
        //如果成功
        resolve(data);
    });
});

p.then(function (value) {
    console.log(value.toString());
}, function (reason) {
    console.log("读取失败!!");
});
```

### 封装AJAX

```js
// 接口地址: https://api.apiopen.top/getJoke
const p = new Promise((resolve, reject) => {
    //1. 创建对象
    const xhr = new XMLHttpRequest();

    //2. 初始化
    xhr.open("GET", "https://api.apiopen.top/getJoke");

    //3. 发送
    xhr.send();

    //4. 绑定事件, 处理响应结果
    xhr.onreadystatechange = function () {
        //判断
        if (xhr.readyState === 4) {
            //判断响应状态码 200-299
            if (xhr.status >= 200 && xhr.status < 300) {
                //表示成功
                resolve(xhr.response);
            } else {
                //如果失败
                reject(xhr.status);
            }
        }
    }
})

//指定回调
p.then(function (value) {
    console.log(value);
}, function (reason) {
    console.error(reason);
});
```

### 深层次封装

```js
// 接口地址: https://api.apiopen.top/getJoke
function ajax(method, url, data) {
    const p = new Promise((resolve, reject) => {
        //1. 创建对象
        const xhr = new XMLHttpRequest();

        //2. 初始化
        xhr.open(method, url);

        //3. 发送
        if (data) {
            xhr.send(data);
        } else {
            xhr.send();
        }

        //4. 绑定事件, 处理响应结果
        xhr.onreadystatechange = function () {
            //判断
            if (xhr.readyState === 4) {
                //判断响应状态码 200-299
                if (xhr.status >= 200 && xhr.status < 300) {
                    //表示成功
                    resolve(xhr.response);
                } else {
                    //如果失败
                    reject(xhr.status);
                }
            }
        }
    })
    return p;
}
//指定回调
ajax("get", "https://api.apiopen.top/getJoke").then(function (value) {
    console.log(value);
}, function (reason) {
    console.error(reason);
});
```

**send方法 API:**

```HTML
https://blog.csdn.net/hsl0530hsl/article/details/88558353
https://www.it1352.com/57836.html
https://developer.mozilla.org/zh-CN/docs/Web/API/XMLHttpRequest/send
```

## Promise then()方法

我们**可以把Promise对象看成是一条工厂的流水线**，对于流水线来说，从它的工作职能上看，它只有三种状态，一个是初始状态（刚开机的时候），一个是加工产品成功，一个是加工产品失败（出现了某些故障）。同样对于Promise对象来说，它也有三种状态：

1. `pending`
   初始状态,也称为未定状态，就是初始化Promise时，调用executor执行器函数后的状态。
2. `fulfilled`
   完成状态，意味着异步操作成功。
3. `rejected`
   失败状态，意味着异步操作失败。

它只有两种状态可以转化，即

- 操作成功
  *pending -> fulfilled*
- 操作失败
  *pending -> rejected*

并且这个状态转化是*单向的，不可逆转*，已经确定的状态（fulfilled/rejected）无法转回初始状态（pending）

**then()调用后返回一个Promise对象，意味着实例化后的Promise对象可以进行*链式调用*，而且这个then()方法可以接收两个函数，一个是处理成功后的函数，一个是处理错误结果的函数。**

如下：

```javascript
//创建 promise 对象
const p = new Promise((resolve, reject) => {
    setTimeout(() => {
        resolve('用户数据');
        // reject('出错啦');
    }, 1000)
});

//调用 then 方法  then方法的返回结果是 Promise 对象, 对象状态由回调函数的执行结果决定
//1. 如果回调函数中返回的结果是 非 promise 类型的属性, 状态为成功, 返回值为对象的成功的值

const result = p.then(value => {
    console.log(value);
    //1. 非 promise 类型的属性
    // return 'iloveyou';
    //2. 是 promise 对象
    // return new Promise((resolve, reject) => {
    //     resolve('ok');
    //     // reject('error');
    // });
    //3. 抛出错误
    // throw new Error('出错啦!');
    throw '出错啦!';
}, reason => {
    console.warn(reason);
});

console.log(result);

//链式调用
p.then(value => {

}).then(value => {

});
```

在这里我们主要关注p.then()方法调用后返回的Promise对象的状态，是`pending`还是`fulfilled`，或者是`rejected`?

**返回的这个Promise对象的状态主要是根据promise1.then()方法返回的值，大致分为以下几种情况：**

1. 如果then()方法中返回了一个参数值，那么返回的Promise将会变成接收状态。
2. 如果then()方法中抛出了一个异常，那么返回的Promise将会变成拒绝状态。
3. 如果then()方法调用resolve()方法，那么返回的Promise将会变成接收状态。
4. 如果then()方法调用reject()方法，那么返回的Promise将会变成拒绝状态。

**转换实例如下：**

```javascript
var promise2 = new Promise(function (resolve, reject) {
    // 2秒后置为接收状态
    setTimeout(function () {
        resolve('success');
    }, 2000);
});

promise2
    .then(function (data) {
    // 上一个then()调用了resolve，置为fulfilled态
    console.log('第一个then');
    console.log(data);
    return '2';
})
    .then(function (data) {
    // 此时这里的状态也是fulfilled, 因为上一步返回了2
    console.log('第二个then');
    console.log(data); // 2

    return new Promise(function (resolve, reject) {
        reject('把状态置为rejected error'); // 返回一个rejected的Promise实例
    });
}, function (err) {
    // error
})
    .then(function (data) {
    /* 这里不运行 */
    console.log('第三个then');
    console.log(data);
    // ....
}, function (err) {
    // error回调
    // 此时这里的状态也是fulfilled, 因为上一步使用了reject()来返回值
    console.log('出错：' + err); // 出错：把状态置为rejected error
})
    .then(function (data) {
    // 没有明确指定返回值，默认返回fulfilled
    console.log('这里是fulfilled态');
});
```

## Promise catch()方法

catch()方法和then()方法一样，都会返回一个新的Promise对象，它主要用于捕获异步操作时出现的异常。因此，我们通常省略then()方法的第二个参数，把错误处理控制权转交给其后面的catch()函数，如下：

```javascript
var promise3 = new Promise(function (resolve, reject) {
    setTimeout(function () {
        reject('reject');
    }, 2000);
});

promise3.then(function (data) {
    console.log('这里是fulfilled状态'); // 这里不会触发
    // ...
}).catch(function (err) {
    // 最后的catch()方法可以捕获在这一条Promise链上的异常
    console.log('出错：' + err); // 出错：reject
});
```

## Promise实践

```js
//引入 fs 模块
const fs = require("fs");

// fs.readFile('./resources/为学.md', (err, data1)=>{
//     fs.readFile('./resources/插秧诗.md', (err, data2)=>{
//         fs.readFile('./resources/观书有感.md', (err, data3)=>{
//             let result = data1 + '\r\n' +data2  +'\r\n'+ data3;
//             console.log(result);
//         });
//     });
// });

//使用 promise 实现
const p = new Promise((resolve, reject) => {
    fs.readFile("./resources/为学.md", (err, data) => {
        resolve(data);
    });
});

p.then(value => {
    return new Promise((resolve, reject) => {
        fs.readFile("./resources/插秧诗.md", (err, data) => {
            resolve([value, data]);
        });
    });
}).then(value => {
    return new Promise((resolve, reject) => {
        fs.readFile("./resources/观书有感.md", (err, data) => {
            //压入
            value.push(data);
            resolve(value);
        });
    })
}).then(value => {
    console.log(value.join('\r\n'));
});
```

## Promise 其他API

### Promise.all()

Promise.all()接收一个参数，它必须是可以迭代的，比如数组。

它通常用来处理一些并发的异步操作，即它们的结果互不干扰，但是又需要异步执行。它最终只有两种状态：*成功或者失败*。

它的状态受参数内各个值的状态影响，即里面状态全部为`fulfilled`时，它才会变成`fulfilled`，否则变成`rejected`。

成功调用后返回一个数组，数组的值是有序的，即按照传入参数的数组的值操作后返回的结果。如下：

```javascript
// 置为fulfilled状态的情况
var arr = [1, 2, 3];
var promises = arr.map(function (e) {
    return new Promise(function (resolve, reject) {
        resolve(e * 5);
    });
});

Promise.all(promises).then(function (data) {
    // 有序输出
    console.log(data); // [5, 10, 15]
    console.log(arr); // [1, 2, 3]
});
// 置为rejected状态的情况
var arr = [1, 2, 3];
var promises2 = arr.map(function (e) {
    return new Promise(function (resolve, reject) {
        if (e === 3) {
            reject('rejected');
        }
        resolve(e * 5);
    });
});

Promise.all(promises2).then(function (data) {
    // 这里不会执行
    console.log(data);
    console.log(arr);
}).catch(function (err) {
    console.log(err); // rejected
});
```

#### all()应用

论坛系统首页：查询所有模块信息，然后根据模块id查询所有的模块数据

```js
// 定义首页路由
router.get("/", function (req, res) {
    // 当我们去渲染index.art的时候,这里面的data数据其实就是从数据库里面查询得到的数据
    var classesModules = [];
    common.getMongoClient().then((client) => {
        var dbo = client.db("newcapec"); // dbo就是指定的数据库对象
        // 先查询所有的模块
        dbo.collection("classesMods").find({}).toArray(async function (err, result) {
            var classesModsArr = result;

            var promises = classesModsArr.map(function (e) {
                return new Promise(function (resolve, reject) {
                    dbo.collection("populars").find({
                        classesId: e._id.toString()
                    }).sort({
                        count: -1
                    }).limit(4).toArray(function (err, popResult) {
                        for (var i = 0; i < popResult.length; i++) {
                            popResult[i]._id = popResult[i]._id.toString();
                        }
                        var obj = {
                            moduleName: e.moduleName,
                            moduleId: e._id.toString(),
                            populars: popResult
                        }
                        resolve(obj);
                    })
                });
            });

            Promise.all(promises).then(function (data) {
                // 所有数据
                console.log(data);
                res.render('index.art', {
                    classesModules: data
                });

                client.close();
            });
           
        })
    })

})
```

### Promise.race()

Promise.race()和Promise.all()类似，都接收一个可以迭代的参数，但是*不同之处是Promise.race()的状态变化不是全部受参数内的状态影响，一旦参数内有一个值的状态发生的改变，那么该Promise的状态就是改变的状态*。就跟`race`单词的字面意思一样，谁跑的快谁赢。如下：

```javascript
var p1 = new Promise(function (resolve, reject) {
    setTimeout(() => {
        resolve('p1 doned');
    }, 300);
});

var p2 = new Promise(function (resolve, reject) {
    setTimeout(() => {
        resolve('p2 doned');
    }, 50);

});

var p3 = new Promise(function (resolve, reject) {
    setTimeout(() => {
        reject('p3 rejected');
    }, 10);
});

var p = Promise.race([p1, p2, p3]);
p.then(function (data) {
    // 显然p2更快，所以状态变成了fulfilled
    // 如果p3更快，那么状态就会变成rejected
    console.log(data); // p2 doned
}).catch(function (err) {
    console.error(err); // 不执行
});
```

### Promise.resolve()

Promise.resolve()接受一个参数值，可以是`普通的值`，`具有then()方法的对象`和`Promise实例`。正常情况下，它返回一个Promise对象，状态为`fulfilled`。但是，当解析时发生错误时，返回的Promise对象将会置为`rejected`态。如下：

```javascript
// 参数为普通值
var p4 = Promise.resolve(5);
p4.then(function(data) {
  console.log(data); // 5
});


// 参数为含有then()方法的对象
var obj = {
  then: function() {
    console.log('obj 里面的then()方法');
  }
};

var p5 = Promise.resolve(obj);
p5.then(function(data) {
  // 这里的值时obj方法里面返回的值
  console.log(data); // obj 里面的then()方法
});


// 参数为Promise实例
var p6 = Promise.resolve(7);
var p7 = Promise.resolve(p6);

p7.then(function(data) {
  // 这里的值时Promise实例返回的值
  console.log(data); // 7
});

// 参数为Promise实例,但参数是rejected态
var p8 = Promise.reject(8);
var p9 = Promise.resolve(p8);

p9.then(function(data) {
  // 这里的值时Promise实例返回的值
  console.log('fulfilled:'+ data); // 不执行
}).catch(function(err) {
  console.log('rejected:' + err); // rejected: 8
});
```

### Promise.reject()

Promise.reject()和Promise.resolve()正好相反，它接收一个参数值`reason`，即*发生异常的原因*。此时返回的Promise对象将会置为`rejected`态。如下：

```javascript
var p10 = Promise.reject('手动拒绝');
p10.then(function(data) {
  console.log(data); // 这里不会执行，因为是rejected态
}).catch(function(err) {
  console.log(err); // 手动拒绝
}).then(function(data) {
 // 不受上一级影响
  console.log('状态：fulfilled'); // 状态：fulfilled
});
```

**总之，除非Promise.then()方法内部抛出异常或者是明确置为rejected态，否则它返回的Promise的状态都是fulfilled态，即完成态，并且它的状态不受它的上一级的状态的影响。**

# 十五、Set集合

**ES6新增for of循环**

```html
for...of 语句创建一个循环来迭代可迭代的对象。在 ES6 中引入的 for...of 循环，以替代 for...in 和 forEach() ，并支持新的迭代协议。for...of 允许你遍历 Arrays（数组）, Strings（字符串）, Maps（映射）, Sets（集合）等可迭代的数据结构等。
for (variable of iterable) {
    statement
}
variable：每个迭代的属性值被分配给该变量。
iterable：一个具有可枚举属性并且可以迭代的对象。
```

## Set概述

​	**ES6 提供了新的数据结构 Set（集合）。它类似于数组，但成员的值都是唯一的，集合实现了 iterator 接口，所以可以使用『扩展运算符』和『for…of…』进行遍历。**

​	Set 对象允许你存储任何类型的唯一值，无论是原始值或者是对象引用。

## Set对象创建

​	我们可以通过构造函数来创建集合；

```js
//创建一个空集合
let s = new Set();

//创建一个非空集合
let s1 = new Set([1,2,3,1,2,3]);
```

## Set对象属性

属性： size     返回实例的成员总数

## Set对象方法

add、delete、has、clear

| 操作方法          | 功能                        |
| ----------------- | --------------------------- |
| set.add(value)    | 添加一个值，返回Set结构本身 |
| set.delete(value) | 删除某个值，返回布尔值      |
| set.has(value)    | 返回布尔值，表示是否是成员  |
| set.clear()       | 清除所有成员，无返回值      |

```javascript
let mySet = new Set();

mySet.add(1); // Set(1) {1}
mySet.add(5); // Set(2) {1, 5}  s.add(1).add(2).add(2); //链式写法
mySet.add(5); // Set(2) {1, 5} 这里体现了值的唯一性
mySet.add("some text");
// Set(3) {1, 5, "some text"} 这里体现了类型的多样性

var o = {
    a: 1,
    b: 2
};
mySet.add(o);
mySet.add({
    a: 1,
    b: 2
});
// Set(5) {1, 5, "some text", {…}, {…}} 
// 这里体现了对象之间引用不同不恒等，即使值相同，Set 也能存储

console.log(mySet.size); //获取数量 5
console.log(mySet.has(3)); //false
console.log(mySet.delete(5)); // false
console.log(mySet.has(2)); //false 

for (let v of mySet) {
    console.log(v);
}
```

## Set对象遍历

| 操作方法      | 功能                     |
| ------------- | ------------------------ |
| set.keys()    | 返回键名的遍历器         |
| set.values()  | 返回键值的遍历器         |
| set.entries() | 返回键值对的遍历器       |
| set.forEach() | 使用回调函数遍历每个成员 |

注意：这里要注意Set的键名和键值是同一个值，所以key()和values()行为是一致的。

```javascript
let set = new Set(['Sure', 'Jacky', 'Rocky']);

for (let item of set.keys()) {
    console.log(item); //Sure Jacky Rocky
}

for (let item of set.values()) {
    console.log(item); //Sure Jacky Rocky
}

for (let item of set.entries()) {
    console.log(item); //['Sure': 'Sure'] ['Jacky': 'Jacky'] ['Rocky': 'Rocky']
}
```

## 类型转换

- Array和Set相互转换

```javascript
// Array 转 Set
var mySet = new Set(["value1", "value2", "value3"]);
console.log(mySet);

// 用...操作符，将 Set 转 Array
var myArray = [...mySet];
console.log(Array.isArray(myArray))
```

- String转换为Set

```js
// String 转 Set
var mySet = new Set('hello');  // Set(4) {"h", "e", "l", "o"}
// 注：Set 中 toString 方法是不能将 Set 转换成 String
```

## Set集合应用

**数组去重**

```js
let arr = [1, 2, 3, 4, 5, 4, 3, 2, 1];
let result = [...new Set(arr)]; // 特性：Set集合元素唯一
console.log(result);
```

**数组去重方法：**https://segmentfault.com/a/1190000016418021?utm_source=tag-newest

**并集**

```js
let arr = [1, 2, 3, 4, 5, 4, 3, 2, 1];
let arr2 = [4, 5, 6, 5, 6];
let union = [...new Set([...arr, ...arr2])];
console.log(union);
```

**交集**

```js
let arr = [1, 2, 3, 4, 5, 4, 3, 2, 1];
let arr2 = [4, 5, 6, 5, 6];
/* let result = [...new Set(arr)].filter(item => {
            let s2 = new Set(arr2); // 4 5 6
            if (s2.has(item)) {
                return true;
            } else {
                return false;
            }
        }); */
// 简写
let result = [...new Set(arr)].filter(item => new Set(arr2).has(item));
console.log(result);
```

**差集**

```js
let arr = [1, 2, 3, 4, 5, 4, 3, 2, 1];
let arr2 = [4, 5, 6, 5, 6];
let diff = [...new Set(arr)].filter(item => !(new Set(arr2).has(item)));
console.log(diff);
```

## Set中的特殊值

Set 对象存储的值总是唯一的，所以需要判断两个值是否恒等。有几个特殊值需要特殊对待：

- +0 与 -0 在存储判断唯一性的时候是恒等的，所以不重复；
- undefined 与 undefined 是恒等的，所以不重复；
- NaN 与 NaN 是不恒等的，但是在 Set 中只能存一个，不重复。

```js
let set = new Set();
set.add(1);
set.add(2);
set.add(+0);
set.add(-0);
set.add(undefined);
set.add(undefined);
set.add(NaN);
set.add(NaN);
console.log(set)
```

## Array和Set的区别

Array数组是表示一种储存在连续空间中的结构类型（内容可以为number,object等）

Set更像是一种抽象的数据类型。它只包含不同的元素/对象，不需要连续分配存储空间。

它们之间最大的差别就是**Array中的元素是可以重复的，而Set中的元素不可重复** 。除此之外，Array被认为是一种索引集合，而Set是一种键的集合。

​	索引集合是指按下标作为索引值排序的数据结构
​	键的集合使用key访问元素，访问顺序与元素插入顺序一致。	

# 十六、Map集合

## Map概述

​	JavaScript的对象只能使用字符串当做key，这给它的使用带来了很大的限制。

​	为了解决这个问题，ES6 提供了 Map 数据结构。它类似于对象，也是键值对的集合。但是“键” 的范围不限于字符串，各种类型的值（包括对象）都可以当作键。map结构提供了value与value的对应关系，是一种更完善的hash结构。

​	Map 也实现了 iterator 接口，所以可以使用『扩展运算符』和『for…of…』进行遍历。

​	Map（）方法和 Set（） 方法用法类似。

​	Map 对象保存键值对。任何值(对象或者原始值) 都可以作为一个键或一个值。

## Map对象属性

属性： size     返回实例的成员总数

## Map对象方法

set、get、delete、has、clear

| 操作方法             | 功能                                          |
| -------------------- | --------------------------------------------- |
| map.set('key',value) | 向map中添加新的键值对 返回的是添加好的map结构 |
| map.get(key)         | 返回key对应的value 否则返回undefined          |
| map.delete(key)      | 删除指定的key 删除成功返回true 否则返回false  |
| map.has(key)         | Map中是否有这个指定的key                      |
| map.clear()          | 清除所有成员，无返回值                        |

```javascript
//key 是字符串
var myMap = new Map();
var keyString = "a string";
myMap.set(keyString, "和键'a string'关联的值");
// 因为 keyString === 'a string'
console.log(myMap.get(keyString)); // "和键'a string'关联的值"
myMap.get("a string"); // "和键'a string'关联的值"


//key 是对象
var myMap = new Map();
var keyObj = {
    classesName: "前端41班"
};
myMap.set(keyObj, ["张三", "李四", "王五"]);
console.log(myMap.get(keyObj)); // "张三", "李四", "王五"
myMap.get({
    classesName: "前端41班"
}); // undefined, 因为 keyObj !== {}

//key 是函数
var myMap = new Map();
var keyFunc = function () {}; // 函数
myMap.set(keyFunc, "和键 keyFunc 关联的值");
console.log(myMap.get(keyFunc)); // "和键 keyFunc 关联的值"
myMap.get(function () {}) // undefined, 因为 keyFunc !== function () {}

//key 是 NaN
var myMap = new Map();
myMap.set(NaN, "not a number");
console.log(myMap.get(NaN)); // "not a number"
var otherNaN = Number("foo");
myMap.get(otherNaN); // "not a number"

//其他方法
var m = new Map();
var o = {
    p: "Hello World"
};
m.set(o, "Jimor")
m.get(o) // "Jimor"

console.log(m.has(o)) // true
console.log(m.delete(o)) // true
console.log(m.has(o)) // false
//虽然 NaN 和任何值甚至和自己都不相等(NaN !== NaN 返回true)，NaN作为Map的键来说是没有区别的。
```

## Map遍历

| 操作方法  | 功能                                     |
| --------- | ---------------------------------------- |
| keys()    | 返回键名的遍历器（类似Java里的Iterator） |
| values()  | 返回键值的遍历器                         |
| entries() | 返回键值对的遍历器                       |
| forEach() | 使用回调函数遍历每个成员                 |

举例说明：

```javascript
 // for...of遍历Map集合
var myMap = new Map();
myMap.set(0, "zero");
myMap.set(1, "one");

for (let v of myMap) {
    console.log(v); // [0, "zero"]、[1, "one"]
}

// 既然知道v代表的是数组,那么我们就可以采用解构。 
for (var [key, value] of myMap) {
    console.log(key + " = " + value); // 0 = zero、1 = one
}

/* 这个 entries 方法返回一个新的 Iterator 对象，它按插入顺序包含了 Map 对象中每个元素的 [key, value] 数组。 */
// console.log(myMap.entries())
for (var [key, value] of myMap.entries()) {
    console.log(key + " = " + value);
}

/* 这个 keys 方法返回一个新的 Iterator 对象， 它按插入顺序包含了 Map 对象中每个元素的键。 */
// 将会显示两个log。 一个是 "0" 另一个是 "1"
for (var key of myMap.keys()) {
    console.log(key);
}

/* 这个 values 方法返回一个新的 Iterator 对象，它按插入顺序包含了 Map 对象中每个元素的值。 */
// 将会显示两个log。 一个是 "zero" 另一个是 "one"
for (var value of myMap.values()) {
    console.log(value);
}

//forEach()
var myMap = new Map();
myMap.set(0, "zero");
myMap.set(1, "one");

// 将会显示两个 logs。 一个是 "0 = zero" 另一个是 "1 = one"
myMap.forEach(function (value, key) {
    console.log(key + " = " + value);
}, myMap)
```

## Map 对象的操作

```js
//Map 与 Array的转换
var kvArray = [
    ["key1", "value1"],
    ["key2", "value2"]
];

// Map 构造函数可以将一个 二维 键值对数组转换成一个 Map 对象
var myMap = new Map(kvArray);
console.log(myMap)

// 使用 Array.from 函数可以将一个 Map 对象转换成一个二维键值对数组
var outArray = Array.from(myMap);
console.log(outArray);

//Map 的合并
var first = new Map([
    [1, 'one'],
    [2, 'two'],
    [3, 'three'],
]);
var second = new Map([
    [1, 'uno'],
    [2, 'dos']
]);

// 合并两个 Map 对象时，如果有重复的键值，则后面的会覆盖前面的，对应值即 uno，dos， three
var merged = new Map([...first, ...second]);
console.log(merged);
```

## Map 和 Object 的区别

Map对象是一种有对应 键/值 对的对象， JS的Object也是 键/值 对的对象 ；

在Object对象中， 只能把String和Symbol作为key值， 但是在Map中，key值可以是任何基本类型(String, Number, Boolean, undefined, NaN….)，或者对象(Map, Set, Object, Function , Symbol , null….);

通过Map中的size属性， 可以很方便地获取到Map长度， 要获取Object的长度， 你只能用别的方法了；

# 十七、面向对象

​	es6之前，javascript本质上不能算是一门面向对象的编程语言，因为它对于封装、继承、多态这些面向对象语言的特点并没有在语言层面上提供原生的支持。

​	但是，它引入了原型(prototype)的概念，可以让我们以另一种方式模仿类，并通过原型链的方式实现了父类子类之间共享属性的继承以及身份确认机制。

​	es6新增了class关键字，用来实现对象的封装和继承。 

## 封装

- es5下是这样的结构：

```javascript
function Animal(name, age) {
    this.name = name;
    this.age = age;
    this.show = function () {
        console.log('Animal.show()==>', name, age);
    }
}
var a1 = new Animal("Tiger", 5);
var a2 = new Animal("Cat", 2);

a1.show();
a2.show();

//每次创建一个构造方法都实例，都要开辟一个空间，属性无所谓，
//大家都是一样都方法就没有必要再创建新的了，太浪费空间了
function Person(name, age) {
    this.name = name;
    this.age = age;
}
Person.prototype = {
    say: function (word) {
        console.log(this.name + "说：" + word);
    },
    play: function (hobby) {
        console.log(this.name + "的爱好是：" + hobby);
    }
}
var p1 = new Person("张三", 20);
var p2 = new Person("李四", 22);

p1.say("你好");
p1.play("篮球");
p2.say("How are you?");
p2.play("football");
```

- es6下和java非常相似

```javascript
// 声明class类
class Student {
    // 定义构造函数,构造函数名字必须叫constructor
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    //方法：方法必须使用该语法, 不能使用 ES5 的对象完整形式
    say() {
        console.log(this.name + "说：我学习很好");
    }
    study() {
        console.log(this.name + "今年" + this.age + "岁，准备学习ES6");
    }
}
let stu = new Student("小明", 22);
console.log('姓名：', stu.name);
console.log('年龄：', stu.age);
stu.say();
stu.study();
```

## 继承

### ES5实现继承：构造函数+原型

```js
//手机
function Phone(brand, price) {
    this.brand = brand;
    this.price = price;
}

Phone.prototype.call = function () {
    console.log("我可以打电话");
}

//智能手机
function SmartPhone(brand, price, color, size) {
    Phone.call(this, brand, price);
    this.color = color;
    this.size = size;
}

//设置子级构造函数的原型
SmartPhone.prototype = new Phone;
SmartPhone.prototype.constructor = SmartPhone;

//声明子类的方法
SmartPhone.prototype.photo = function () {
    console.log("我可以拍照")
}

SmartPhone.prototype.playGame = function () {
    console.log("我可以玩游戏");
}

const chuizi = new SmartPhone('锤子', 2499, '黑色', '5.5inch');

console.log(chuizi);
```

### ES6实现继承

```javascript
class Phone {
    //构造方法
    constructor(brand, price) {
        this.brand = brand;
        this.price = price;
    }
    //父类的成员属性
    call() {
        console.log("我可以打电话!!");
    }
}

class SmartPhone extends Phone {
    //构造方法
    constructor(brand, price, color, size) {
        super(brand, price); // Phone.call(this, brand, price)
        this.color = color;
        this.size = size;
    }

    photo() {
        console.log("拍照");
    }

    playGame() {
        console.log("玩游戏");
    }
    // 重写父类继承过来的方法
    call() {
        console.log('我可以进行视频通话');
    }
}

const xiaomi = new SmartPhone('小米', 799, '黑色', '4.7inch');
// console.log(xiaomi);
xiaomi.call();
xiaomi.photo();
xiaomi.playGame();
```

## 实例对象和函数对象

​	**实例对象：通过 new 函数产生的对象称为实例对象，简称对象。**

​	**函数对象：将函数作为对象使用时**

```js
function Fn() {

}
const fn = new Fn()
console.log(fn);  
console.log(Fn.prototype)
console.log(Fn.bind())
```

首先定义一个函数，即 Fn 是一个函数。接着 new Fn()，说明 Fn 是一个构造函数。

此时 fn 是 Fn 的实例对象，简称对象。因此第一条打印语句输出的就是一个对象。

接着 Fn.prototype，每创建一个函数，该函数都会自动带有一个prototype属性。按语法格式来看这里的 Fn 应该是一个对象，但是它又是一个函数，这个时候我们就把 Fn 称为函数对象。若有 Fn.prototype.add()，此时 add 称为原型对象上的方法。

## 静态成员

### ES5定义静态成员

```js
function Phone() {

}
Phone.name = '手机';
Phone.change = function () {
console.log("我可以改变世界");
}
Phone.prototype.size = '5.5inch';

let nokia = new Phone();

console.log(nokia.name);
// nokia.change();
console.log(nokia.size);
```

### ES6定义静态成员

```javascript
class Phone {
    //静态属性
    static name = '手机';
    static change() {
        console.log("我可以改变世界");
    }
}

let nokia = new Phone();
console.log(nokia.name);
console.log(Phone.name);
```

**小结：**

1. class可以用来声明一个类
2. 类中的成员方法直接声明，而不再使用function关键字，但是不能定义私有变量和函数
3. 支持静态成员
4. 和es5相比，es6在语言层面上提供了面向对象的部分支持，虽然大多数时候只是一个语法糖，但使用起来更方便，语意化更强、更直观，同时也给javascript继承提供一个标准的方式。还有很重要的一点就是－es6支持原生对象继承。

## get和set

当我们获取属性或设置属性的时候，想要执行某个行为；

```js
// 当我们获取属性或设置属性的时候，想要指向某个行为；
class Student {
    constructor(name, sex, uage) {
        this.name = name;
        this.sex = sex;
        this.uage = uage;
    }
    // 当我们获取
    get age() {
        // console.log("获取年龄");
        if (this.sex == "女") {
            return "女孩子的年龄是不能暴露"
        } else {
            return this.uage;
        }

    }

    set age(newAge) {
        if (newAge > 100 || newAge <= 0) {
            console.log("年龄不符合");
        } else {
            this.uage = newAge;
        }

    }
}

const s1 = new Student("张三", "男", 21);
const s2 = new Student("小美", "女", 20);

s1.age = 16
// s2.age = 102
// console.log(s1, s2);

console.log(s1.age);
console.log(s2.age);
```

# 十八、数值扩展

## Number.EPSILON

Number.EPSILON 是 JavaScript 表示的最小精度

EPSILON 属性的值接近于 2.2204460492503130808472633361816E-16

```js
function equal(a, b) {
    if (Math.abs(a - b) < Number.EPSILON) {
        return true;
    } else {
        return false;
    }
}
console.log(0.1 + 0.2 === 0.3);
console.log(equal(0.1 + 0.2, 0.3))
```

## 二进制和八进制

ES6 提供了二进制和八进制数值的新的写法，分别用前缀 0b 和 0o 表示。

```js
//ES6 之前没有二进制表示法
//ES 不同版本八进制表示法区别很大
let b = 0b1010;
let o = 0o777;
let d = 100;
let x = 0xff;
console.log(x);
```

## Number.isFinite() 

Number.isFinite() 用来检查一个数值是否为有限的

```js
// Number.isFinite  检测一个数值是否为有限数
console.log(Number.isFinite(100));
console.log(Number.isFinite(100 / 0));
console.log(Number.isFinite(Infinity));
```

## Number.isNaN()

Number.isNaN() 用来检查一个值是否为 NaN

```
// Number.isNaN 检测一个数值是否为 NaN 
console.log(Number.isNaN(123));
```

## Number.parseInt() / Number.parseFloat()

ES6 将全局方法 parseInt 和 parseFloat，移植到 Number 对象上面，使用不变。

```js
//Number.parseInt Number.parseFloat字符串转整数
console.log(Number.parseInt('5211314love'));
console.log(Number.parseFloat('3.1415926神奇'));
```

## Number.isInteger()

```js
// Number.isInteger 判断一个数是否为整数
console.log(Number.isInteger(5));
console.log(Number.isInteger(2.5));
```

## Math.trunc()

用于去除一个数的小数部分，返回整数部分。

```js
//Math.trunc 将数字的小数部分抹掉  
console.log(Math.trunc(3.5));
```

##  Math.sign()

```js
//Math.sign 判断一个数到底为正数 负数 还是零
console.log(Math.sign(100));
console.log(Math.sign(0));
console.log(Math.sign(-20000));
```

# 十九、对象方法扩展

ES6 新增了一些 Object 对象的方法 

1) Object.is 比较两个值是否严格相等，与『===』行为基本一致（+0 与 NaN） 

2) Object.assign 对象的合并，将源对象的所有可枚举属性，复制到目标对象 

3) `__proto__`、setPrototypeOf、 setPrototypeOf 可以直接设置对象的原型 

```js
//1. Object.is 判断两个值是否完全相等 
console.log(Object.is(120, 120)); // true
console.log(Object.is(NaN, NaN)); // true
console.log(NaN === NaN); // false

//2. Object.assign 对象的合并
// 用来合并配置项非常有用
const config1 = {
    host: 'localhost',
    port: 3306,
    name: 'root',
    pass: 'root',
    test: 'test'
};
const config2 = {
    host: 'http://www.newcapec.com.cn/',
    port: 33060,
    name: 'newcapec',
    pass: 'root',
    test2: 'test2'
}
console.log(Object.assign(config1, config2));

//3. Object.setPrototypeOf 设置原型对象  Object.getPrototypeof
// 不推荐,还是用原来的原型方式
const school = {
    name: '新开普'
}
const cities = {
    xiaoqu: ['北京', '上海', '深圳']
}
Object.setPrototypeOf(school, cities);
console.log(Object.getPrototypeOf(school));
console.log(school);
```

# 二十、ES6模块化

## 模块化概述

模块化是指将一个大的程序文件，拆分成许多小的文件，然后将小文件组合起来。

### 模块化的好处

模块化的优势有以下几点： 

1) 防止命名冲突 

2) 代码复用 

3) 高维护性 

### 模块化规范产品

ES6 之前的模块化规范有： 

1) CommonJS => NodeJS、Browserify 

2) AMD  => requireJS 

3) CMD => seaJS

## ES6 模块化语法

模块功能主要由两个命令构成：export 和 import。 

​	export 命令用于规定模块的对外接口 

​	import 命令用于输入其他模块提供的功能

### export语法

#### 分别暴露

```js
export let school = '新开普';

export function teach() {
    console.log("我们可以教给你开发技能");
}
```

#### 统一暴露

```js
let school = '新开普';

function findJob(){
    console.log("我们可以帮助你找工作!!");
}

export {school, findJob};
```

#### 默认暴露

```js
export default {
    school: 'Newcapec',
    change: function(){
        console.log("我们可以改变你!!");
    }
}
```

### import语法

```html
<script type="module">
    //1. 通用的导入方式
    //引入 m1.js 模块内容
    import * as m1 from "./src/js/m1.js";
    // //引入 m2.js 模块内容
    import * as m2 from "./src/js/m2.js";
    // //引入 m3.js 
    import * as m3 from "./src/js/m3.js";
    console.log(m1);
    m1.teach();
    console.log(m2);
    m2.findJob();
    console.log(m3);
    m3.default.change();

    //2. 解构赋值形式
    import {school, teach} from "./src/js/m1.js";
    import {school as newcapec, findJob} from "./src/js/m2.js";
    import {default as m3_1} from "./src/js/m3.js";
    console.log(school);
    teach();
    console.log(newcapec);
    findJob();
    console.log(m3_1);
    m3_1.change();

    //3. 简便形式  针对默认暴露
    import m3_2 from "./src/js/m3.js";
    console.log(m3_2);
</script>
```

#### 统一入口文件引入

​	开发中，我们肯定不会使用上述方式引入，我们一般会提供统一的入口文件；

```js
 <script src="./src/js/app.js" type="module"></script>
 
 // app.js
 //入口文件
//模块引入
import * as m1 from "./m1.js";
import * as m2 from "./m2.js";
import * as m3 from "./m3.js";

console.log(m1);
console.log(m2);
console.log(m3);

m1.teach();
m2.findJob();
m3.default.change();
```

# 二十一、环境兼容

​	主流的一些前端框架都采用了ES6的语法，随着时间的推移，支持度已经越来越高了，超过 90%的 ES6 语法特性都实现了。考虑到客户的浏览器跨度太大，我们还是要是用一些工具，将ES6编译成ES5

​	在这里，推荐使用Babel。 Babel是一个广泛使用的 ES6 转码器，可以将 ES6 代码转为 ES5 代码，从而在现有环境执行。这意味着，你可以用 ES6 的方式编写程序，又不用担心现有环境是否支持。

 https://blog.csdn.net/qq_31411389/article/details/51958332?utm_source=blogxgwz2

## Babel转码步骤

```html
1. 安装工具 npm i babel-cli babel-preset-env browserify -D
2. 编译 npx babel src/js -d dist/js --presets=babel-preset-env
3. 打包 npx browserify dist/js/app.js -o dist/bundle.js
```

```html
<script src="dist/bundle.js"></script>
```

## 引入NPM包

通过npm intsall安装之后，通过improt引入NPM包即可；

```js
//修改背景颜色为粉色
import $ from 'jquery';// const $ = require("jquery");
$('body').css('background','pink');
```
