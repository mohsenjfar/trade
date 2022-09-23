[Go back to getting started](../Getting_started.md) |
[Course content online](https://www.coursera.org/learn/node-js/home/welcome)
___

- [Introduction to serverside JavaScript](#introduction-to-serverside-javascript)
  - [Welcome to Developing Cloud Applications with Node.js and React](#welcome-to-developing-cloud-applications-with-nodejs-and-react)
  - [Getting started with Node.js](#getting-started-with-nodejs)
    - [Full-stack application](#full-stack-application)
    - [Open Source and cross-platform](#open-source-and-cross-platform)
    - [V8 Engine](#v8-engine)
    - [Event-driven, Asynchronous, Non-blocking, Single-Threaded](#event-driven-asynchronous-non-blocking-single-threaded)
    - [JSON Payload](#json-payload)
    - [Express Framework](#express-framework)
  - [Introduction to Node.js](#introduction-to-nodejs)
  - [Introduction to Server-Side JavaScript](#introduction-to-server-side-javascript)
  - [Creating a Web Server with Node.js](#creating-a-web-server-with-nodejs)
  - [Working with Node.js Modules](#working-with-nodejs-modules)
  - [Module 1 Summary](#module-1-summary)
  - [Glossary - Introduction to Server-Side JavaScript](#glossary---introduction-to-server-side-javascript)
  - [Cheatsheet - Introduction to Server-Side JavaScript](#cheatsheet---introduction-to-server-side-javascript)
- [Asynchronous I/O with callback programming](#asynchronous-io-with-callback-programming)
  - [Asynchronous I/O with Callback Programming](#asynchronous-io-with-callback-programming-1)
  - [Creating Callback Functions](#creating-callback-functions)
  - [Promises](#promises)
  - [Working with JSON](#working-with-json)
  - [An introduction to Async Await](#an-introduction-to-async-await)
  - [Module 2 Summary](#module-2-summary)
  - [Glossary - Asynchronous I/O with Callback Programming](#glossary---asynchronous-io-with-callback-programming)

# Introduction to serverside JavaScript

## Welcome to Developing Cloud Applications with Node.js and React

welcome to Developing Cloud Applications with Node.js and React. In this course, you will focus on server-side JavaScript and frameworks. You will discover ways to make development faster and easier in web browsers and embedded systems. You may ask, what is the relevance of developing cloud applications with Node.js and React and why should you care? In 2020, a survey done by Stack Overflow found Node.js was used by more than 50% of the developers who answered the survey, making it one of the most used frameworks in web development. React.js similarly ranked second in the usage category. So, as you can tell, both of these frameworks are very popular in server-side and client-side application development. This course is designed to help you achieve success in this fast-growing cloud computing area. You may be an IT person looking to step up in your career, a new graduate seeking to establish a solid skillset to score a job in cloud or web development, an IT decision maker who needs to manage more cloud-centric projects, or someone in another field who wants to be able to talk about cloud computing knowledgeably. In the course learning and labs, you will develop your first web servers. You'll see examples of where to apply your new skills in real-life applications where you make remote web server calls requesting for information, and then using this information in your web application. You'll also learn how to make your applications more responsive by using asynchronous callbacks and promises. You'll learn how to make low-level HTTP requests using Node.js and then add Express.js as an abstraction layer. This course introduces ways for you to extend your server-side applications with imported modules and third-party packages. You will practice using the Express Node.js web application framework to build a web server and build dynamic content with middleware, routing, and templating. As you become more adept at server-side development, you'll discover how to work with front-end frameworks including React. You'll combine all you know about server-side cloud app development to request, receive, and dynamically change information. So there's lots to cover here! To get the most from this course, view every video, check your learning with each quiz, and connect to your peers in the discussion forums. Reaffirm your new skills by completing the labs and build a winning portfolio. Take the next step along this exciting journey that leads to a world of possibilities and good luck!

## Getting started with Node.js

### Full-stack application

When we talk about full-stack application, it includes:

- the client side
  - the website, the mobile application that are user facing
- the server side
  - which actually process any request from the client side and processes it and sends a response to the client. In today's world, the cloud hosts the web server, application server and database.

### Open Source and cross-platform

Javascript has an ideal choice in client side to perform validation of the HTML Pages for a long time. Given the ease of use and understanding, Javascript language was extended to also server-side coding. This is Node.js. It is an open-source language. You don't need any special licenses to use Node.js and many packages and libraries are contributed to NodeJS, as it open source. Node.js code, once written, can run on linux, windows and Mac OSX.

### V8 Engine

Any code that you write needs to be processed and converted to machine-understandable form. The javascript code uses V8 engine from Google to do this. V8 is Google's open source high-performance engline. All the Google chrome browsers come with v8 engine. Node.js also uses v8 engine.

### Event-driven, Asynchronous, Non-blocking, Single-Threaded

Processes in a server can be single-threaded or multi-threaded. <mark>Single-threaded</mark> is where **only one command is processed at a given point of time**. <mark>Multi-threaded</mark> is where **multiple commands are processed simultaneously**. Node.js is single-threaded, which means it can only do one process at one time. That might make it sound like it is not appropriate for server-side coding. But Node.js is <mark>asynchronous</mark> and non-blocking. This means, **when a process is happening, the program doesn't have to wait until the process fininshes**. Node.js is <mark>event-driven</mark>. When Node.js performs an I/O operation, like reading from the network, accessing a database or the filesystem, **an event is triggered** and instead of blocking the thread and wasting the processor time waiting, Node.js will **resume the operations when the response comes back** or in other words, the reseponse event occurs. During that time, the server is not blocked and can do other things, which make it looks like it is multi-threading.

### JSON Payload

<mark>JSON</mark> stands for **Java script Object Notation**. The JSON is in **key value pair**. <mark>Payload</mark> is **the data transmitted between the client and the server**. JSON object is a bunch of key-value pairs. When the client needs to send data to the server, it sends it in the form a JSON object. Look at the example below.

```
{
"name":"John",
"age":"24",
"email":"johnparker@gmail.com"
}
```

### Express Framework

While Node.js has packages to create a server, <mark>express framework</mark> makes it very simple to **create API end-points**. API <mark>end-point</mark> is the **specific point of entry for the requests from client to the server**.

## Introduction to Node.js

Welcome to Introduction to Node.js! After watching this video, you will be able to: Describe the role of Node.js for server-side scripting. List the differences between JavaScript and Node.js. Describe Express.js and explain how Express.js helps developers build Node.js apps. <mark>Node.js</mark> is **an open-source language that runs on V8**. Being open source, means that node.js can run on Linux, Windows, and Mac OSX. <mark>V8</mark> is **an open source engine that was developed by Google for the Google Chrome browser**. Developers often use JavaScript for client-side functionality. Node.js is the server component in the same language. Node.js is event-driven and uses asynchronous, non-blocking I/O. With server-side JavaScript, Node applications process, and route web service requests from the client. In <mark>step 1</mark>, the user selects an option in the user interface, **written in HTML and CSS**. In <mark>step 2</mark>, this action by the user **triggers JavaScript code** that implements the business logic on the client-side, for example, input validation. In <mark>step 3</mark>, the **JavaScript application makes a web service call over HTTP with a JSON data payload**. The **REST web service**, which is part of a node.js application running on the node server, **receives the HTTP request**. In <mark>step 4</mark>, the **REST web service processes the request and returns the result to the client as a JSON payload over HTTP**. Although developers can still use JavaScript for browser functionality in frameworks, such as angularJS, Dojo, and jQuery, they can now use Node.js in the same components of the architecture where they use Java, Perl, C++, Python, and Ruby. Node.js is used in production by companies, such as Uber, Yahoo!, LinkedIn, GoDaddy, eBay, and PayPal. It is event-driven and uses asynchronous, non-blocking I/O. <mark>Express.js</mark> is **a highly configurable framework for building applications on Node.js**. It **abstracts lower-level APIs in Node.js by using HTTP utility methods and middleware**. Before you build your first Node.js app, let’s get familiar with the <mark>IDE and some key Node.js concepts</mark>. Express.js simplifies application development on Node.js. The following features enable you to develop your application quickly: <mark>Public</mark>: **public assets like image, CSS, and javascript**. <mark>Templates/views</mark>: **server-rendered HTML that is sent back to the client in response to requests**. <mark>Routes</mark>: **defines endpoints that accept and process client requests**. <mark>Server.js</mark>: **a file which contains the main application code**. <mark>Package.json</mark>: **contains metadata information about the project including dependencies, scripts, and so on**. In this video, you learned that: Node.js is the server-side component of JavaScript. Using Node.js can improve application performance and express.js is a framework that helps you build Node.js applications

## Introduction to Server-Side JavaScript

Welcome to Introduction to server-side JavaScript. After watching this video, you will be able to: Explain the purpose of the Node.js JavaScript framework and explain the differences between client-side JavaScript and server-side JavaScript. JavaScript is one of the main languages used in the World Wide Web. It was originally built to add dynamic behavior to static websites on clients where there were primarily browsers. JavaScript is an interpreted language. You do not need to compile JavaScript applications before running them. Although the language syntax resembles Java, it is not derived from the Java programming language. JavaScript can now be run on different servers and embedded systems and all modern web browsers support JavaScript. Developers build responsive, interactive web applications with hypertext markup language (HTML), cascading style sheets (CSS), and JavaScript. With a text editor and a web browser, you can quickly write, test, and debug JavaScript applications. With client-side JavaScript, developers create rich, interactive web applications in the web browser. In step 1, the user interface is rendered using HTML and CSS. When the user selects an option in the web page, it triggers business logic written as a JavaScript application. The JavaScript application sends a web service request using JavaScript Object Notation (JSON) over hypertext transfer protocol (HTTP). On the server, a Representational State Transfer (REST) web service intercepts the call. This service traditionally would be written in Java, PHP: Hypertext Preprocessor (PHP), or another backend language. In the last step, the application server processes the web service request using a server-side application such as Enterprise Java components and returns to the client. With server-side JavaScript, Node.js applications process, and route web service requests from the client. Compare the following diagram with the one in the previous slide. Most of the steps are identical. In step 1, the user selects an option in the user interface, which is written in HTML and CSS. In step 2, the option triggers a JavaScript application that implements the business logic on the client-side. In step 3, the JavaScript application makes a web service call over HTTP with a data payload written in JSON. In step 4, a REST web service intercepts the HTTP request and in the final step, instead of invoking an Enterprise Java application, the Node.js server hosts an application written in the JavaScript language. This code written in JavaScript runs on the server, and not in the client's web browser. In this video, you learned that: Node.js is a server-side programming framework that uses JavaScript as its programming language. With server-side JavaScript, Node.js applications process and route web service requests from the client and Node.js is for developers who want to build scalable, concurrent server applications quickly with a minimal set of tools.

## Creating a Web Server with Node.js

Welcome to Creating a Web Server with Node.js. After watching this video, you will be able to: Describe the characteristics of Node.js and write a simple web server with Node.js. Node.js is a server-side programming framework that uses JavaScript as its programming language. Many developers are already familiar with the JavaScript language. It is built with a heavy emphasis on concurrent programming with a lightweight language. Node.js is a single-threaded application environment that handles input/output (I/O) operations through events. Instead of blocking on asynchronous I/O operations, you write callback functions to handle results when they complete. Node.js is suited for developers who want to build scalable and concurrent server applications by using features like callback functions and the Node.JS runtime event loop. These features of the JavaScript language and the Node.js runtime enable quick development with a minimal set of tools. Every JavaScript file is a module in Node.js. A module corresponds to a script file. A package can contain one or more nodes. The Node.js runtime is packaged with many utility modules that you can use to create and extend your applications. With the HTTP Node.js module, you can develop an application that listens to HTTP requests and returns HTTP response messages. To create an instance of a web server, use the HTTP.createServer function. The web server is stored in a variable called "server." The createServer function takes in an optional callback function as a parameter. This callback function handles the incoming request message and provides an appropriate response message. The callback function shown here is anonymous. After you create an instance of the server object, you can set the server to listen to a specific port. For example, call the HTTP.listen function with a parameter of 8080 as the port to set the server to listen on 8080. In this video, you learned that: Node.js is a single-threaded application environment that handles I/O operations through events. Every JavaScript file is a module in Node.js and with the HTTP Node.js module, you can develop an application that listens to HTTP requests and returns HTTP response messages.

## Working with Node.js Modules

Welcome to Working with Node.js Modules. After watching this video, you will be able to: Describe Node.js packages. Import Node.js modules into your script. Export functions and properties from a module, and access exported properties from a module. A package consists of one or more modules. The package.json file describes details about a Node.js module. If a module does not have a package.json file, Node.js assumes that the main class is named index.js. To specify a different main script for your module, specify a relative path to the Node.js script from the module directory. This is an example of a package.json file. The name and version fields form a unique identifier for the module; for example, today-1.0.0. The main field lists a path to the main Node.js script; in this example, the today.js script in the lib subdirectory. Package.json defines many other fields. For example, license states the module's usage rights. You can use the require function to import a Node.js module. The require statement assumes that scripts have a file extension of .js. The require function creates an object that represents the imported Node.js module. In this example, a Node,js script file that is named today.js is in the same directory as your application. When you call require with the name of a subdirectory, Node.js looks for a script file with the same name as the subdirectory. If the script file does not exist, the function assumes that the name is the name of a directory and looks for a script named index.js within that directory. To import a Node.js module that consists of a single script, use the require function with a relative path to the script file. In this example, the main application is in the Node.js script file. Hello.js makes a require function call to the today.js script file. This example uses the same hello.js Node.js file. The Node.js module is saved in a directory named mod_today. The actual script file is saved in index.js. When hello.js makes a call to the require function in the mod_today directory, the script file checks whether there is a file named index.js. This is the default name for a script in a Node.js module. Each Node.js module has an implicit exports object. To make a function or a value available to Node.js applications that import your module, add a property to exports. In this example, the dayOfWeek property is added to the exports object. Then, dayOfWeek is assigned an anonymous function that returns the day of the week. For example, if the dayOfWeek function returns 1, this value maps to Monday. When you import a Node.js module, the require function returns a JavaScript object that represents an instance of the module. For example, the today variable is an instance of the today Node.js module that is called "today." To access the properties of the module, retrieve the property from the variable. In the same example, today.dayOfWeek represents the current exported property from the today Node.js module. In this video, you learned that: Every package has a package.json file that describes details about a Node.js module. To make a function or a value available to Node.js applications that import your module, add a property to the implicit exports object and when you import a Node.js module, the require function returns a JavaScript object that represents an instance of the module.

## Module 1 Summary

- Node.js is a server-side programming framework for developers who want to build scalable, concurrent server applications quickly with a minimal set of tools. 
- With server-side JavaScript, Node.js applications process and route web service requests from the client. 
- With Node.js, you write asynchronous callback functions to handle results when they complete. 
- The Node.js runtime is packaged with many utility modules that you can use to create and extend your applications. 
- A Node.js package consists of one or more modules. 
- You can use the package.json file to specify a different main script for your module with a relative path to the Node.js script from the module directory. 

##  Glossary - Introduction to Server-Side JavaScript

- [Click here](../Developing%20Cloud%20Native%20Applications/Assets/C4M1%20Glossary%20v1.1%20APPROVED.pdf) to view and download "Introduction to Server-Side JavaScript" module glossary

## Cheatsheet - Introduction to Server-Side JavaScript

- [Click here](../Developing%20Cloud%20Native%20Applications/Assets/C4M1%20cheat%20sheet%20v1.2.pdf) to view and download "Introduction to Server-Side JavaScript" module cheatsheet

# Asynchronous I/O with callback programming

## Asynchronous I/O with Callback Programming

Welcome to Asynchronous I/O with Callback Programming. After watching this video, you should be able to: Explain the concept of asynchronous callback functions and handle inbound hypertext transfer protocol (HTTP) method calls for a server resource. Network operations run in an asynchronous manner. For example, the response from a web service call might not return immediately. When an application blocks (or waits) for a network operation to complete, that application wastes processing time on the server. Node.js makes all network operations in a non-blocking manner. Every network operation returns immediately. To handle the result from a network call, write a callback function that Node.js calls when the network operation completes. This sequence diagram for a scenario shows the interaction between the application, the Node.js framework, the web service call to the remote server, and the call back to the callback function. In the first step, the application makes a call to HTTP.request. This function makes a call to the remote web server and requests the web service. Before the Node.js framework receives the HTTP response message from the remote web server, it immediately returns a result for the HTTP.request function call. This result simply indicates that the request message was sent successfully. It does not say anything about the response message. When the Node.js framework receives an HTTP response message from the remote server, it calls the callback function that you defined during the HTTP.request function call. This function handles the HTTP response message. In a slightly more complex scenario, your application calls a custom Node.js module, which then makes an HTTP.request function call. The Node.js framework then calls the remote server's web service by sending an HTTP request message. In the same manner as in the first scenario, the Node.js framework returns a value to the HTTP function call in the Node.js module. This response simply states that the HTTP request was successfully sent out. The Node.js module then returns from the exported function call. At this point, the application continues processing on to the next step, while the response message has not yet been sent. When the remote server returns an HTTP response message, the Node.js framework calls the callback function defined by the custom Node.js module. The purpose of the callback function is to handle two events: request.on('data') and request.on('end'). In this case, the callback function simply prints the HTTP response message body to the console log. This code example shows you how to make an HTTP request call from a function inside a Node.js module. The first parameter in the HTTP request function is an options variable. The options variable included at least two variables: the hostname of the remote server, and a uniform resource locator (URL) resource path that you want to act upon. In the example here, you are making a call to the US National Weather Service to retrieve the weather observation from San Francisco International Airport (KSFO). The second parameter of the HTTP request function is a callback function. In this case, it is an anonymous function that receives one parameter: the response object. When the Node.js module calls this anonymous function, events occur while it is receiving parts of the HTTP response object. In this example, there are two specific events: a 'data' event and an 'end' event. For these two events, you define more callback functions to handle each event type. In the actual coding, you may need to use HTTPS instead of HTTP. The result object is passed into the callback function of a parseString module. The HTTP.request function takes in a URL and a set of options. If both are passed, the two are merged, with options taking precedence. You can define the host, ports, authentication, protocol, and other headers in the options object. The HTTP.request method also accepts an optional callback function that is invoked immediately once a response is received. When HTTP.request calls the callback function, it passes a response object in the first parameter of the callback function. This callback function has the response object as the first parameter. The Node.js framework emits several events during the course of the request function. You can listen to these events by using the object.on() method and passing in the event name as the first parameter. If the request is successful, a 'data' event is emitted on the response object every time data comes in, followed by an 'end' event when the response finishes. If the request fails, there is an 'error' event followed by the 'close' event. Let's see how to handle such errors. The request method returns an object of type HTTP.ClientRequest. This object represents the request in progress. You can append to the request body, make changes to the headers, and listen for error events as shown here. The code simply outputs the error message if there is an error. To end the request, call clientRequest.end(). In this video, you learned that: When an application blocks for a network operation to complete, that application wastes processing time on the server. Node.js makes all network operations in a non-blocking manner. and when the Node.js framework receives an HTTP response message from the remote server, it calls the callback function that handles the HTTP response message.

## Creating Callback Functions

Welcome to Creating Callback Functions. After watching this video, you should be able to: Create a callback function to intercept hypertext transfer protocol (HTTP) method calls. As an asynchronous framework, Node.js makes extensive use of callback functions to return the result to the calling function. Node.js modules in the software development kit (SDK) pass an error object as the first parameter in a callback function. Here, the function is defined with an error as the first parameter. With this convention, the callback function checks if the first parameter holds an error object. If error is defined, the callback function handles the error and cleans up any open network or database connections. If error is not defined, then the callback function examines the result from the call. If error is defined, print the error message. Otherwise, the weather.current function call completed successfully. Print the result from the function call. The codes are in the main app, which has a weather object (the Node.js module) that calls the weather’s current function. The location is an input parameter: in this example, an airport. To print temp_f in the browser, we can use response.end(`The current weather reading is ${temp_f} degrees’). Now we’ll look at an example of passing an error object to the callback function. Recall how callback functions check the first parameter to see if an error condition occurred. Instead of printing the result in the console, you call the resultCallback callback function with the error object. You pass back the error object to the resultCallback callback function of the main application. If no error occurred, you call the resultCallback function with null as the first parameter. The codes are in the custom Node.js module. The callback handler printed the contents of the HTTP response message body to the console. What if you wanted it to return the response message to the original calling application? If you use a return function, Node.js might call the callback function after the http.request() call completes. The application calls the exported function. The module that implements the function calls http.request so that the Node.js framework can make a web service call on its behalf. When that request is sent successfully, the framework returns control to the Node.js module. Then the Node.js module returns control to the application. When the remote server sends back a HTTP response message to the Node.js framework, the framework calls the callback handler that was defined by the Node.js module. However, there is no connection between the callback function and the main application. so how do you link the callback function to the main application? The pattern is that when one Node.js application calls a module in a non-blocking manner, the application provides a callback function to process the result. If the main application calls http.request(), it must provide a callback handler to process the HTTP response message. If the main application calls a function that calls http.request(), there are two callback functions: The custom module has a callback function that handles the HTTP response message from http.request(). And the main application has a callback function that processes the result captured in the first callback function. Let’s see how this solution works. We’ll create a callback function to capture the result from the http.request function call. The application makes a call to the Node.js module. The Node.js module makes an http.request function call in order to send an HTTP request message to a remote server. Before the remote service returns an HTTP response message, the http.request function call returns control to the Node.js module as the request message was successfully sent. Then the Node.js module replies with a value to the main application. At a future point, the remote server sends back an HTTP response message. The Node.js framework calls the callback function defined by the Node.js module. This callback function calls another callback function defined by the main application. Having one callback function invoke another callback function is the only way to pass a message from the Node.js module to the main application when the Node.js module receives a response message. Here, when the main application calls weather.current(), it passes an anonymous callback function to process the result from the call. In this case, the anonymous function “function (temp_f)” takes in one input parameter, temp_f. The purpose of this callback function is to take the weather reading in degrees Fahrenheit and print the result in the console log. The resultCallback callback function in the function of the custom Node.js module links to the anonymous callback function, function (temp_f), of the weather object’s .current function in the main application. Now you can see a Node.js module that returns a result to the main application with a callback function. Here, a function is defined for the property named "current." This property will be exported as part of the module. The anonymous function takes a parameter named "resultCallback" from the main application. This is how you pass a reference to the main application's callback function to the Node.js module's callback function. The resultCallback parameter stores the anonymous callback function from the main application. Look at the bottom of the current property. A "response.on('end')" event handler handles the transmission of the HTTP response message. When the remote server finishes sending back the response message, the code makes a call to resultCallback and passes it the current weather reading in degrees Fahrenheit. This is how you pass a value from one callback handler to another. In this video, you learned that: Node.js makes extensive use of callback functions to return the result to the calling function. Node.js modules in the SDK pass an error object as the first parameter in a callback function. and there is one callback function at each level.

## Promises

Welcome to Promises. After watching this video, you will be able to:​ Define promises. Explain the different states of a promise and describe how to use promises with asynchronous methods. A promise is an object returned by an asynchronous method. The promise has three states, which are pending, resolved, and rejected. Promises are most useful for application programming interface (API) requests, input/output (I/O) operations, and other operations that are time consuming and can block resources. A method can be defined to return a promise object, if you know it is going to take time for execution and thereby block resources. When you call a method that returns a promise, a promise object is created. The initial state of the promise is the pending state. It is in this state until the operation is complete or some error has caused the operation to abort. When the operation is complete, the promise is said to be resolved. When there is an error, the promise is said to be rejected. You can also create a promise object if you know that the operations you are going to perform could be blocking. In this example, methCall is a promise which is fulfilled or rejected depending on whether the file is successfully read or not. You can see on the output screen that the content of the file is read if the filename is valid and displayed. In this case the promise is resolved. If the filename is invalid, the promise is rejected and the error message is displayed. You know that hypertext transfer protocol (HTTP) requests when called synchronously can be blocking. There are many packages in the Node.js ecosystem that wrap promises around HTTP requests. The axios package is one such package to handle HTTP requests. It returns a promise object. The status of the promise until it hears back from the uniform resource locator (URL) requested is pending. The promise object has a "then" method which is called after the promise is fulfilled. The catch is executed if the promise is rejected. In this example, you first pass a valid URL. It creates a pending promise. Once the promise is fulfilled, then the response is logged on the console. Next, you pass an invalid URL. This also creates a promise object which is pending. This promise will be rejected. This state is being dealt with in the catch block. You can see the console log for the resolve and reject. In this video you learned that: A promise is an object that is returned by an asynchronous method. The initial state of the promise object is the pending state. The axios package is used in Node.js to handle HTTP requests and you can create a promise if you know that the operations could be blocking.

## Working with JSON

Welcome to Working with JSON. After watching this video, you should be able to: Parse JavaScript Object Notation (JSON) data from a hypertext transfer protocol (HTTP) message. JSON is the standard format for application programming interface (API) data exchange. It is the standard representation of native JavaScript objects, and Node.js handles it easily. In this example, the object consists of attribute-value pairs. The first attribute is "Company" and the value is "IBM". The second attribute is "Country" and the value is "USA". The third attribute is "Headquarters" and the value is "Armonk, New York". To parse a JSON string to a JavaScript object, use method JSON.parse. Method JSON.stringify() converts a JavaScript object to a JSON string. Now that you know what JSON is and two important methods that you can use to parse a string into JSON and also convert JSON into a string. Let us see an example of using a real endpoint that returns JSON. You can use JSON to find out how many astronauts are in the International Space Station (ISS). You have found that the number of astronauts is five. In this video, you learned that: Node.js handles JSON easily, and you can use two important methods to parse a string into JSON and also convert JSON into a string.

## An introduction to Async Await

As you might have already learnt, Java Script is a single-threaded scripting language. That means the process can happen only sequentially and no two processes can happen simultaneously. This is a big deterrent to any language and JS solved this by introducing asynchronous programming through Promises. We have learnt about promises and seen some examples of the same. While Promises solved the issues with synchronous programming, nested then can compilcate the structure and readability of the code. In ES 2017, Async/Await was introduced which addressed this issue and gave way to cleaner, readable code. We will understand the working of async/await in the light of the some examples we used for Promise, for better understanding. By awaiting a promise, we can process the result as and when the promise is fulfilled (or rejected).  

In the following code sample, we have created a Promise with a callback where we handle reolve and reject.

```
const axios = require('axios').default;

const connectToURL = (url)=>{
  const req = axios.get(url);
  console.log(req);
  req.then(resp => {
      let listOfWork = resp.data.work;
      listOfWork.forEach((work)=>{
        console.log(work.titleAuth);
      });
    })
  .catch(err => {
      console.log(err.toString())
  });
}
console.log("Before connect URL")
connectToURL('https://reststop.randomhouse.com/resources/works/?expandLevel=1&search=Grisham');
console.log("After connect URL")
```  

We will see how the same is accomplished with async/await.  

```
const axios = require('axios').default;
const connectToURL = async(url)=>{
    const outcome = axios.get(url);
    let listOfWork = (await outcome).data.work;
    listOfWork.forEach((work)=>{
      console.log(work.titleAuth);
    });
}

console.log("Before connect URL")
connectToURL('https://reststop.randomhouse.com/resources/works/?expandLevel=1&search=Grisham').catch(err=>console.log(err.toString()));
console.log("After connect URL")
```  

The best use of async/await can be realized when we have a scenario where some async methods have to happen in sequence. Taking the same example as above, let's first get a list of all books ids by an author and based on book ids, send request to get the details of each book. So, these two actions have to happen one after the other but asynchronously. These can be accomplished with or wothout async/await. But chaining actions is much cleaner with async await, as you can observe below. In actual situations, the nesting can be multiple level and rendering the code difficult to read and maintain. In such situations, we could use async/await.  

The below code is done by nesting the second set of promises into the first.  

```
const axios = require('axios').default;

/*
In the following code we try to get list of all book ids from remote url and then based on that make request about each of the 
id. Finally print them all out. We are using axios get, which returns a promise. 
*/
const connectToURL = (url)=>{
  const req = axios.get(url);
  req.then(resp => {
      let listOfWork = resp.data.work;
      return listOfWork.map((work)=>{
          return work.workid
      })
    }).then((workids)=>{
        let promisesArr = [];
        workids.forEach((workid)=>{
            const req = axios.get("https://reststop.randomhouse.com/resources/works/"+workid);
            promisesArr.push(req);
            req.then(resp=>{
                console.log(resp.data.titleAuth);
            })
        });
    })
  .catch(err => {
      console.log(err.toString())
  });
}
connectToURL('https://reststop.randomhouse.com/resources/works/?expandLevel=1&search=Grisham');
```  

The same objective is attained using async/await.  

```
const axios = require('axios').default;

/*
In the following code we try to get list of all book ids from remote url and then based on that make request about each of the 
id. Finally print them all out. We are using axios get, which returns a promise. 
*/
async function connectToURL(url){
    const resp = await axios.get(url);
    let listOfWork = resp.data.work;
    let workids = listOfWork.map((work)=>{
          return work.workid
    });
    workids.forEach(async (workid)=>{
            const req = await axios.get("https://reststop.randomhouse.com/resources/works/"+workid);
            console.log(req.data.titleAuth);

    });
}
connectToURL('https://reststop.randomhouse.com/resources/works/?expandLevel=1&search=Grisham').catch(err => {
    console.log(err.toString())
});
```  

You can only await a promise inside an async method. This is because await blocks the thread. This will defeat the primary purpose. So the sunction within which an await is used HAS TO BE async.  

## Module 2 Summary

- Network operations run in an asynchronous manner and can block your JavaScript code if not handled properly
- To handle the result from a network call, you can write a callback function that Node.js calls when the network operation completes.
- If you have multiple asynchronous calls, there must be a callback function for each level.
- Promise objects are most useful for operations that are time-consuming and can block resources.
- JSON.parse() and JSON.stringify() are two methods used to handle JSON objects.

## Glossary - Asynchronous I/O with Callback Programming

- [Click here](./Assets/C4M2%20Glossary%20v1.1%20APPROVED.pdf) to view and download "Asynchronous I/O with Callback Programming" module glossary