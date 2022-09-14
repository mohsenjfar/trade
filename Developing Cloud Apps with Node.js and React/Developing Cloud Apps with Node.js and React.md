[Go back to getting started](/IBM%20Full%20Stack%20Software%20Developer/Getting_started.md) |
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