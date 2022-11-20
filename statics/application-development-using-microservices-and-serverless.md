[<=](../index.md) |
[Course content online]()
___

# Introduction to MicroServices

## Welcome to Application Development using Microservices and Serverless

Welcome to this introductory course on microservices and serverless. My name is Alex Parker. This course is designed for all kinds of Cloud practitioners, including anyone who wants to design, develop, deploy, manage or secure applications and solutions on public, private or hybrid cloud platforms. By the end of this course, you will have a solid foundation for microservices and serverless and will have deployed microservices on the cloud and integrated them with serverless compute. The emergence of cloud computing has brought about a lot of changes to modern software development. Rather than large annual releases on physical mediums like CDs, modern software is increasingly released on the cloud, provided cost reduction, decreased time to market, and increased agility. These changes allow organizations to keep pace with their competitors and bring new innovations to market in ways that previously would have been unthinkable. In addition to methodologies like agile and DevOps, microservices have emerged as an architectural model suited for cloud development. Rather than building large applications, known as monoliths, that perform all the functionality, microservices break down larger applications into smaller pieces that are independently maintainable and scalable, providing a host of benefits. This architecture is used at the largest software organizations in the world because it provides cost benefits, team autonomy, and so many other advantages. Likewise, serverless has emerged as an increasingly popular compute option in the cloud era. Giving developers and operators the ability to run applications without managing underlying infrastructure has freed up resources at organizations that can now focus on developing business logic and furthering the mission and goals of their organization, rather than having to maintain servers and complex infrastructure. The Cloud Native Computing Foundation—known as CNCF—conducts annual surveys to discern where and how cloud-native technologies are being adopted. The 2020 survey indicates that just under a third of respondents are already using serverless in production, with 21% evaluating it and 14% planning to use it in the next 12 months. Serverless is positioned to become an even larger force in cloud computing in the years ahead because of its myriad advantages, and understanding its purpose is vital for any cloud developer.This course will introduce you to 12-factor apps and microservices, concepts that emerged to help organizations work better and faster in a cloud-native manner. You’ll then learn about serverless computing—how it works, what value it brings, and what are specific serverless technologies. You’ll get hands-on with IBM Cloud Functions, a serverless platform on IBM Cloud that lets you develop serverless apps with ease. And finally, you’ll learn about tools like Red Hat OpenShift and service meshes, which make the adoption of microservices easier and more secure. The course contains several hands-on labs, which allow you to apply the content you learn. Don't worry if you don't have a machine with sufficient resources, as we provide a cloud-based environment at no charge for completing the hands-on labs. The prerequisites for this course include basic computer and cloud literacy as well as an understanding of core cloud concepts. In addition, understanding of the command line and how to use shell commands will greatly benefit you during this course. 

## Twelve-Factor App

Welcome to ”Twelve-Factor App Methodology.” After watching this video, you will be able to: Describe characteristics of modern software development, describe the goal of twelve-factor apps, identify the twelve factors and describe how these factors map to three phases of the software delivery lifecycle. In modern software development, software is often delivered as a service. Software is centrally hosted and accessed through the internet. This software is often called a web app or software-as-a-service, which is abbreviated SaaS. You have likely used a variety of web apps within the last day! When you use the internet to book reservations or file your taxes, you are interacting with a web app. The twelve-factor app methodology is suited for these types of applications. Microservices are not a requirement for twelve-factor apps. However, microservices are often used in conjunction with the twelve-factor application methodology. Twelve-factor app methodology is designed to ensure that applications are ready for cloud-native deployment. Twelve-factor app methodology enables automation for developers. Applications should be maximally portable across various execution environments and deploy on modern clouds so that servers and systems administrators are not needed. Applications development and production environments should remain as similar as possible to enable continuous application development. Finally, twelve-factor apps should be scalable without requiring significant change or effort. The twelve factors can be grouped into the **code, deploy, and operate phases** of the software delivery lifecycle. We’ll start with the three factors that map to the `code phase` of the software delivery lifecycle. First is **Factor 1, Codebase**. The codebase for an application should always be tracked in a version control system, such as Git. There is a one-to-one relationship between a codebase and an app. An app should be contained in a single codebase. However, there will be multiple deploys, or instances, of the app. While the codebase is the same across those deploys, different app versions can be present in each deploy. For example, dev or test environments can have changes that have not yet reached production. Next is **Factor 5: Build, release, run**. This phase demonstrates how a codebase becomes a production deploy. The **build stage compiles the code, gathers dependence, and then transforms the codebase into an executable unit called a build.** The **release stage combines the build with the deployment’s current configuration so that the code is ready to run**. Then, the **run stage implements the application**. These three stages should be strictly separated. For example, the code should not be changeable at runtime as that would prevent those changes from being included in the build stage. **Factor 10 is dev/prod parity**. This factor minimizes the differences between development and production environments, which is necessary to enable continuous delivery so that changes are quickly promoted into production. This action reduces the chance that code runs appropriately in one environment but not in another. Parity is especially important for backing services. If you use a MySQL database in production, you should use the same MySQL database in your development environments. This helps catch failures earlier in the development process. The first `deploy factor` we’ll discuss is **Factor 2, Dependencies**. An app is only as reliable as its least reliable dependency. As a result, twelve-factor apps do not rely on the implicit existence of any packages or dependencies. All dependencies must be explicitly declared. This way, when a new developer grabs the codebase, there is no assumption that any dependencies already exist on her machine. Next is **Factor 3, Config**. The configuration is everything that can differ between deployments. Different databases are likely used in staging and production, so a developer should configure the credentials and the location of that database per deploy. Sometimes developers store configuration as constants in their code, but this should be avoided since configurations might differ among environments. Config should be strictly separate from code since code doesn’t vary across deploys but config does. Store the Config within environment variables, which are easy to change across deploys without changing the code. **Factor 4 is Backing services**. A twelve-factor app should not distinguish between local and third-party services. Both should be accessible via a URL and credentials, so that a developer can easily swap out the backing service without changing code. For example, if a database experiences problems, a new database can be spun up and substituted in without having to change code. **Factor 6 is Processes**. An app executes in an environment as one or more processes. Processes should be stateless and share nothing. Persistent data needs to be stored in a backing service like a database, since memory and filesystems aren’t shared across processes. If another process handles a subsequent transaction, the subsequent transaction won’t have access to data within the prior process. As a result, data needs to be centrally stored. **Port binding is Factor 7**. When you create a web-facing service, a webserver should not be injected into an application at runtime. Instead, the web app should export HTTP by binding to a port and listening to incoming requests on that port. Port binding can be used for HTTP and other services. Binding a port is generally done in the code by declaring a webserver library as a dependency. Subsequently, because these apps are accessible via a URL, these apps can become backing services for other apps. **Factor 9, Disposability**, specifies that application processes require minimal startup time and should end gracefully when terminated. Quick startup lets us quickly deploy changes to code or config. We can also easily scale apps because new deploys start quickly. **Factor 11 dictates how to handle logs**. Logs give visibility into application performance. An app should not concern itself with storing logs. Rather, an application environment should handle logs as a stream of events that are written to “stdout.” The execution environment can capture the log streams for all running apps, aggregate the log streams, and route the log streams to their destination. This action is especially helpful when the destination is a log analysis tool. Next are `operate` factors. Let’s begin with **Factor 8, Concurrency**. Processes are first-class citizens in a twelve-factor app, because they are the unit of execution. An application runs concurrent processes to handle increased load. Since processes are stateless and share nothing, an application can start additional processes to handle incoming requests and load without creating interdependencies among processes. You can add or subtract processes to handle concurrency needs. Finally, the last factor is **Factor 11: Admin processes**. Admin processes are one-off processes used for managing an app, such as a database migration. Admin processes run against a release, using the same codebase and config. Additionally, the code should include admin processes so that the admin processes remain synchronized with the app. In this video, you learned that: Modern software development often delivers centrally hosted, web-based, Software as a Service applications, twelve factor app methodology enables developers to create more efficient SaaS applications, and the twelve factors maps to the code, deploy, and operate stages of the software delivery lifecycle.

### Read also
- [Twelve-Factor App Methodology](https://12factor.net/)

## What are Microservices?

Welcome to what are microservices. After watching this video, you'll be able to describe what microservices are compared to monolithic applications, explain the drawbacks of using a monolithic architecture, and explain the benefits provided by using a microservices architecture. Next, hear Dan Bettinger from the IBM Cloud team describe what microservices are and explain the advantages of microservices. For those who don't know, a `microservice` is **an application architecture that takes every application function and puts it in its own service, that runs in the container, and these containers they communicate over APIs**. To better understand microservice, we should probably look and understand what a monolith is. A monolithic architecture is a server-side system based on a single application. In a Java world for example, the application would be put into a JAR or WAR file and deployed as a whole into a production environment. The thing about a monolith is, they're easy to develop, deploy and manage. But things happen over time. Let's use an example. In this case, pretend we are a ticketing service. One that sells tickets to sporting events and concerts, etc. In a monolithic world, the architecture might look like this, where we have a user interface, we have some semblance of an inventory component, a recommendation engine that provides outputs based on user inputs, maybe a cart service. We have a payment service and then some type of reporting function to generate reports. That's great. The thing you can realize right off the bat is that these are highly dependent systems or highly dependent software, meaning that there are shared libraries within this architecture. If you make a change, you have to understand what other components rely on those libraries, so they're easier to break over time. Another challenge we have around monoliths are that they're language and framework dependent. In this case, if this is a Java application, any additional component that has to be written needs to be written in Java, so you're somewhat limited by decisions made in the past. Another thing that happens and another challenge with monolith is growth. Over time, user input comes back into the product team and the need to add additional functionality. Initially it's small but over time, you might need to add capability A or capability B for example, or capability C. Now as a whole, the application is getting much larger, it's harder for a team to actually understand what's happening to it, and hard for a team to note every little intricacy about the thing as it grows. As it also becomes bigger, it takes heroic efforts to deploy the monolith, meaning that on a Friday night, you would have to shut down the original application and then actually deploy the new production application and the apps team would spend all weekend trying to stabilize it and get it to run so on Monday it can be up and functional again. That can be very painful for teams and can be really hard. Another challenge we have around monoliths is the way they scale. If it's really busy, and there's lots of people trying to buy tickets in this example, maybe that payment part of the application is under duress and it needs some additional capabilities. What would happen is, you'll have to redeploy the whole application to help satisfy that demand and that need. In this instance, we would need to go ahead and redeploy another version of this system. What that looks like is right now, so we have one system running. When this is under contention, we deploy another version of that application. There's number 2. The challenge is, it might take a lot of time to you go add that new instance of the application, and by the time it's up and running, that peak may have already subsided, and effectively, you've done nothing to help your users. That's a challenge around the monolith as well. Let's look at the same example of the ticketing company in the microservices based environment. Again, in microservice environment, we'd have the same functionality, you'd have your user interface, it would be in its own container as a service, you'd have your inventory service as well, your recommendation engine would be in its own service, your cart is in its service, we had the payment service and we had reporting. It's the same as the monolith. The difference is these all talk over APIs and right off the bat you can see something it's interesting. Because they're independent, the team responsible for the reporting engine for example, can choose a language and framework that they want to use themselves. They are not beholden to choices made by the team that run the cart, or UI, or the payment system. That's really good. It gives those teams flexibility, so that's the language part. Another benefit is the ability to iterate. Because these are independent components and they just talk over APIs, the team responsible for the reporting engine for example, can commit code that goes to the DevOps pipeline, and once it gets tested and it's proven to work it can automatically be deployed to the environment. Thereby, these teams can iterate as fast as they need to bringing value to the customers. That's fantastic. Additionally, these changes are minimal at best. If there is an instance where a service does fail, the rest of the application is still functional, so that's less risk. We also can scale these independently, meaning that in the case where there's a user or a number of users that drive load, and that payment service needs some additional help, what needs to happen is the system can actually add capability automatically just for that particular service until that load subsides. Eventually, what happens is when the load goes back to its regular cadence for example, those systems and those additional services can scale back to normal. Again just to reiterate, the microservices architecture is where every application function is its own service deployed inside of the container environment, they communicate via APIs, it got a language and framework independent, we iterates at will through DevOps pipeline. This reduces some of the risks that we see and then we can scale these components independently. In this video, you learned that microservices make each application component its own service and each service communicates via an API. Microservices allow application components to use different technology stacks. Microservices enable individual components to scale in response to demand and microservices lessen risks associated with change, because components can iterate independently. Failures in one service do not necessarily impact other services.

## Advantages of Microservices

Welcome to “Service Oriented Architecture and Microservices Compared.” After watching this video, you will be able to: Explain what a service oriented Architecture is and describe the differences of purpose and scope between service oriented architecture and microservices. Microservices are used and discussed extensively in cloud computing today. But another concept called Service Oriented Architecture, or SOA, is often compared to microservices. There is much debate and discussion about which of these two architectures to use. To understand the comparison with SOA, here’s a recap of microservices. A microservices architecture aims to completely decouple app components from one another so that components are independently maintained, scaled, and more. Rather than having one large application in a silo that performs all functions, microservices decompose the individual application into smaller applications. Those smaller applications work together to perform the function of one large application. For example, an airline ticketing application that uses a microservices architecture could look like a group of independent components. The application would need several components, such as an application that looks up flights, an application that calculates fares, and an application that books the flight. Each component can use different technology stacks, which is illustrated here by displaying different colors. Each component can scale independently based on the demand for that component, shown here with differing heights for the applications. For example, more people browse airline sites than purchase tickets. Thus, the allocateSeats microservice has three instances, and the adjustInventory microservice has two instances. Service oriented architecture defines a method that enables software components reusability via service interfaces. These interfaces use defined common communication standards to incorporate new applications without performing repeated time-consuming integrations. In this illustration, the displayed services are units of work used by graphical user interfaces, or GUIs. The GUIs are an orchestration layer that strings together sequences of services to create complete business processes. These services expose data that are relevant to the business. This process enables the reuse of services across business processes so that many applications can plug into the same data without repeating the integration process. Each service in an SOA contains the code and data integrations required to execute a complete, discrete business function such as checking a customer’s credit, calculating a monthly loan payment, or processing a mortgage application. Service interfaces provide loose coupling, meaning that each service interface is called with little or no knowledge of how the integration is implemented. The services are published so developers can find those services quickly and reuse those same services to assemble new applications. SOA provides many benefits. First, SOA enables applications to be assembled from reusable services rather than rewrite and reintegrate each time, enabling greater business agility and faster time to market. Services, in the context of the business functions, are understood easily. For example, a service could generate an insurance quote. By matching the application to the business function, business analysts work more closely with developers to understand the scope of a business process and the implications of changing a process. Let’s compare the scope of SOA and microservices. SOA and microservices couple components differently and have different ranges of use. SOA is an enterprise-wide concept that enables exposure of existing applications over loosely-coupled interfaces. Each application corresponds to a business function. SOA enables applications in one part of an extended enterprise to reuse functionality in other applications. In contrast, microservices architecture is an application-scoped concept. Microservices enable the functions within a single application existing as small pieces of code that can be independently changed, scaled, and administered. Microservices do not define how applications talk to one another. How applications in an enterprise communicate with one another is more relevant to SOA. To summarize the differences, SOA focuses on reusing existing application components, resulting in multiple applications across an enterprise using the same services. Microservices focus on decomposing monolithic apps into smaller services, which results in more flexible and faster development of individual applications. In this video, you learned that: SOA is an architecture that focuses on reusing components that perform common business functions, and that SOA is used across applications in an enterprise, whereas microservices are used within an application.

## Microservices Patterns and Anti-Patterns

Welcome to "Microservices Patterns and Anti-Patterns.” After watching this video, you will be able to: Describe several patterns you can use with microservices, and explain anti-patterns not to follow when using microservices. Microservices have numerous patterns available that enable more efficient dev-ops. Let's look at several commonly used patterns. With the convergence of more powerful browsers, faster networks, and client-side languages, many web interfaces began to incorporate all functionality into single-page applications. The user enters through one interface that never reloads the landing page or navigates away from that initial experience. Built using a combination of HTML, CSS, and JavaScript, these applications respond to user input through dynamic service calls to backing REST-based services that update portions of the screen instead of redirecting to an entirely new page. This application architecture often simplifies the frontend experience with the tradeoff of more responsibility on the backing services. While a single-page application works well for a single channel user experience, a single page application pattern delivers poor results across user experiences across different channels, like mobile and web. A `Backend for Frontend pattern` inserts a layer between the user experience and the resources that the experience calls on. For example, an app used on a desktop will have different screen size, display, and performance limits than a mobile device. The BFF pattern allows developers to create and support one backend type per user interface using the best options for that interface, rather than supporting a generic backend that works with any interface, but that potentially negatively impacts front end performance. This diagram illustrates a great use case for a Backend for Frontend application architecture. Say that a user can access an application via a mobile app or a web application on your desktop. Using a BFF pattern, you develop a backend specifically for the mobile experience and another backend specifically for the web experience. Each backend knows how to call the correct services and orchestrate code to optimize the requested channel's experience. The mobile app might display a more limited subset of data, and the screen sizes are different from the web experience. Each backend is a microservice. Instead of having a monolithic app that checks which channel is needed and then contains all the logic to prepare the user experience for that channel, you apply microservice architecture to separate the monolithic backend into distinct services that perform their specific, necessary tasks. The `Strangler pattern` helps manage the refactoring of a monolithic application in stages. The pattern gets its metaphorical name from the garden phenomenon of a vine that strangles a tree. Think of a web application built using individual URLs that map functionally to different aspects of a business domain. With the Strangler pattern, you use the structure of a web application to split an application into multiple functional domains and replace those domains with a new microservices-based implementation for one domain at a time. These two aspects form separate applications that exist side-by-side in the same URL space. Over time, the newly refactored application replaces the original application until finally, you can shut off the monolithic application. The Strangler Pattern includes these steps: **First, transform**. Create a parallel new site on a cloud platform or within your existing environment. Next, **coexist**. Leave the existing site functional and live for a specified time. Incrementally redirect from the current location to the new site for newly implemented functionality. Finally, **eliminate**. Remove the outdated functionality from the existing site, or simply stop maintaining that functionality when you redirect traffic from the original site. Numerous patterns are available that help address some of the more common challenges and opportunities associated with transitioning to and using microservices. Learning more about recommended microservice patterns is worthwhile. While there are many patterns for creating effective microservices, there are an equally significant number of patterns that can quickly get any development team into trouble. Next, learn about these `anti-patterns`, also referred to as microservices "dont’s." The first rule of microservices is, don't build microservices. Stated more accurately, **don't start with microservices**. Microservices are ideal for managing application complexity when the applications are too large and unwieldy to update and maintain easily. When you determine that the monolithic application's complexity negatively affects application development and maintenance, consider refactoring that application into smaller services. **Always use microservices with DevOps or cloud services**. Building out microservices means building out distributed systems, and distributed systems can be difficult and time-consuming. Implementing microservices without proper deployment and monitoring, automation, or managed cloud services that support your now sprawling, heterogenous application infrastructure creates numerous, unnecessary complications. Avoid implementing too many microservices by making those **microservices too small**. If you go too far with implementing the "micro" in microservices, you can easily find yourself with development overhead and complexity that outweighs the overall gains. It's better to lean toward larger services and then only break them apart when they start to develop characteristics that microservices solve. Break apart larger services when deploying changes becomes complicated and slow, the common data model is overly complex, or when parts of the service have differing load and scale requirements. In this video, you learned that: Microservices enable single-page applications that rely on backing services to update the page dynamically, backend for frontend patterns use microservices to facilitate different user experiences more easily, apply the Strangler pattern to help break up monolithic apps into microservices, only use microservices when needed, use microservices with DevOps and Cloud services, and build microservices to the right size and not overly small.

### Read also
- [14 software architecture design patterns to know](https://www.redhat.com/architect/14-software-architecture-patterns)

## Lab
- [Click here](./instructional-labs.pdf) to see lab content.
## Module Summary

- Twelve factor app methodology maps to the code, deploy, and operate stages of the software delivery lifecycle enabling developers to create more efficient and more easily maintained SaaS applications​
- Service oriented architecture, used across enterprise-wide applications, is an architecture that focuses on reusing components that perform common business functions. 
- Microservices decouple app components into their own services so that they can be independently maintained, scaled, and more. Each service communicates via an API​. Microservices enable application components to use different technology stacks​ and scale to demand.
- Microservices lessen risks associated with change because components can iterate independently​. Failures in one service do not necessarily impact other services​
- Microservice patterns provide structure that reduces reinventing solutions for commonly encountered challenges. Backend for Frontend patterns use microservices to facilitate different user experiences more easily while the Strangler pattern can help break up monolithic apps into microservices.

# Introduction to Serverless

## What is Serverless?

Welcome to “What is Serverless?” After watching this video, you will be able to: define serverless computing, explain why there are servers in serverless computing, identify attributes of serverless, Explain why serverless is fundamentally about spending more time on code and less on infrastructure. Serverless is an approach to computing that offloads responsibility for common infrastructure management tasks to cloud providers and tools, enabling engineers to focus their time and effort on the business of logic specific to their applications or process. Let’s dig deeper into this topic. Serverless strives for zero operational considerations. With cloud providers managing operations, developers can return their attention to writing applications that focus on business logic. Imagine if teams could spend all their time developing better applications instead of managing operational tasks. To accomplish the goal of zero operational considerations, cloud providers take responsibility for a variety of labor-intensive server management tasks. These tasks include maximizing compute, memory, and networking utilization, as well as minimizing compute costs. All the operations are guaranteed, including scaling, low latency, high availability, multi-region, monitoring, logging, and security. Having developers spend more time on applications greatly benefits organizations. Developers can optimize their apps, build cleaner code, perform better testing, add additional features, and improve the user experience. The biggest controversy around serverless is around the name itself. Although the name could indicate that no servers are involved, there are servers in serverless computing. Applications and code require server space. The name “serverless” has persisted because the name describes an end user’s experience. In a technology that is described as “serverless,” the management needs of the underlying servers are invisible to the end user. The servers are still there, you just don’t see them or interact with them. Let’s review a few `key attributes of serverless` computing. Here’s the first attribute: **Serverless requires no management or operation infrastructure**, which enables developers to focus more narrowly on business logic. Next, **code runs on-demand on a per-request basis**. Scaling is performed transparently with the number of requests served. If there are no requests, then there is no need for the application to run. But as requests come in, the application scales up to handle them. The last attribute is that serverless computing **enables end-users to pay only for the resources used** and never for idle capacity. Since the application scales up as needed, end-users do not pay during periods of inactivity. In this video, you learned that: Infrastructure management is invisible for end users with serverless computing. Serverless computing enables developers to focus on the business-specific needs in their applications. Serverless code runs on-demand and scales transparently. Pay-as-you-go server consumption means that users never pay for idle capacity. 

## Serverless Pros and Cons

Welcome to “Serverless Pros and Cons” After watching this video, you will be able to describe the benefits and challenges associated with serverless computing. With serverless computing, cloud providers take on a large share of the work, which brings many `benefits`. First, there are **no infrastructure requirements** for end users because they are using someone else’s infrastructure. This means that end users have no servers to maintain. Cloud providers are also responsible for the infrastructure reliability, which includes servers, networking, storage, and more. Serverless architectures are quite fault-tolerant since cloud providers ensure reliability. **Developers benefit because they can focus on coding** instead of coding and infrastructure management. This benefit lets developers do what they enjoy and do best. From a financial perspective, serverless computing benefits end **users as they are charged on a per-request basis**. End users are only billed for what they use. This means that for certain workloads, such as those that require parallel processing, serverless can be faster and more cost-effective. However, serverless computing is not best for every situation; and serverless computing does have some `constraints`. For example, while many organizations can realize significant cost savings if their applications have spiky workloads, organizations with workloads characterized by **long-running processes** won’t realize the same benefits from the pay-per-use model. Users with long-running workload might find that a traditional server environment is more cost-effective. Serverless architectures are designed to take advantage of an ecosystem of managed cloud services. As an architectural model, **serverless isn’t as portable as a virtual machine or a container**. For some companies, deeply integrating with the native managed services of cloud providers is where much of the value of cloud is found. For other organizations, these patterns can lead to **unwanted vendor lock-in risks**. Serverless architectures often restart processes, which is known as a **cold start**. This is due to frequent scaling up and down. For time-critical applications, such as banking applications, even low levels of latency are unacceptable. **Monitoring is complex** in any distributed system as there are a variety of interrelated dependencies, like microservices, that need to be monitored together, rather than monitoring a single application. As software increasingly uses microservices and serverless architectures, monitoring and debugging can become even more complex as requests and failures need to be traced among various services running in different environments. For example, you may not know whether an error originated in one microservice or another, so you must trace the request through multiple services to locate the point of failure. Another challenge is that serverless platforms don’t necessarily support every programming language. Serverless platforms often support several popular programming languages, but if you need to write a function in an **unsupported language**, you can’t use serverless computing for that workload. However, you can use containers with any language or framework. In this video, you learned that serverless architectures remove the need for infrastructure management and are reliable, because cloud providers ensure fault-tolerance. You also learned that serverless is well-suited for spiky workloads that can afford some latency, but that long-running applications are better run elsewhere. Finally, you learned that serverless can lead to vendor lock-in and doesn’t always support every programming language.

## What is Function as a Service?

Welcome to “What is function as a Service?” After watching this video, you will be able to define Function as a Service, referred to as FaaS, describe FaaS capabilities and benefits, and identify the differences between FaaS and serverless. `What is Function as a Service?` Function as a Service, known as FaaS, is **an event-driven computing model, which means that code is executed in response to events**. Like serverless, FaaS abstracts away infrastructure management so that developers can focus on building, running, and managing application packages as functions. Functions are stateless software that run customized logic for business purposes. **Application code is typically packaged as a container and runs in response to events or requests**. As discussed with serverless, functions scale down to zero when there are no requests. Function run only in response to incoming requests. Functions manage server-side logic and state. For instance, a function wouldn’t generally serve a front-end web page, but the function would be triggered on the server-side in response to a user action on the front end. Function-as-a-service sounds a lot like serverless, and people often use the two terms interchangeably. But **FaaS is a subset of serverless computing** and is one way to implement serverless. As a result, the characteristics of serverless are true of function-as-a-service. Both are pay-per-use, involve no infrastructure management, and allow developers to focus on developing their apps. But while serverless is focused on any service category where configuration, billing, and management of servers are invisible to the end-user. Serverless focuses on any service category where configuration, billing, and management of servers are invisible to the end-user. This includes compute, storage, database, API gateways, and others. Function-as-a-service, while perhaps the most central technology in serverless, focuses on event-driven computing. The benefits of function-as-a-service are easy to list because they are largely the same as the benefits of serverless computing that we already discussed. Function-as-a-service lets developers focus on code and not infrastructure; lets teams pay only for the resources they use when they use them; scales up and down automatically; and provides high availability. For a real-world example, consider the scenario where you need to upload a profile picture to a website. The website might also require a thumbnail of that image for displaying on certain webpages. When a user uploads a photo to the site, this image is uploaded to an object storage bucket. This event triggers an IBM Cloud function that is designed to take that image and create a thumbnail image. The function also stores the thumbnail image in object storage so that if needed, the website can access the thumbnail image. This is a common situation in which function-as-a-service is used. Here’s another example that explains how functions can integrate with microservices architectures: Traditionally, a monolithic application performed all of the actions. While this programming method was feasible, the method crammed a lot of functionality into a single application. The resulting code was difficult to parse and maintain. Now, programmers can use microservices to implement the bulk of the application, such as the web front end and account management capabilities. Functions are ideal for simple capabilities performed when specific events occur. When the account management microservice uploads a new picture, programmers can have a high level of confidence that the thumbnail will be created automatically by the function. In this video, you learned that: FaaS, a subset of serverless computing, is an event-driven computing execution model. Highly available, microservices compatible, FaaS applications consist of stateless, scalable, customized containers. FaaS is ideal for spiky workloads, pay-as-you-go capabilities often results in cost savings. FaaS enables developers to focus on business needs

## The Serverless Stack

Welcome to “The Serverless Stack” After watching this video, you will be able to: Describe why FaaS is a foundational technology in the serverless stack. Summarize how object storage serverless framework, and explain how event streaming, messaging, and API gateways fit in the serverless stack. **Serverless is a set of common attributes**. **Serverless is not an explicit technology**. Therefore, many technologies are considered serverless since they possess shared characteristics, such as pay-per-use and no infrastructure management. Function-as-a-service is one example of serverless technology. That’s why FaaS seems so much like serverless—because FaaS is ultimately an implementation of serverless attributes. FaaS is an excellent example of serverless. FaaS is widely understood as the originating technology in the serverless category. **FaaS represents the core compute** and processing engine in serverless and sits in the center of most serverless architectures. To illustrate that concept, consider that functions can perform custom logic and fire in response to events generated by other services in the stack. However, there are also other technologies in the serverless stack. Like other architectures, serverless architectures have a data layer for any data persisted by the applications. Databases and storage are the foundation of the serverless data layer.A serverless approach to these technologies involves transitioning away from provisioning “instances” with defined capacity, connection, and query limits and moving toward models that scale linearly with demand in both infrastructure and pricing. To explain the **database layer** with a bit more detail, organizations that use a traditional server environment often provision a specific database, or multiple instances of that database, on servers in a datacenter. In that situation, the size of the servers limits the size of the database. The organization must pay for that server whether the server is full of data or contains only a small amount of data. Limiting capacity and disregarding usage is clearly incompatible with a serverless model in which storage capacity is not limited, and you pay only for exactly what you use. The next part of the serverless stack is **object storage**. Object storage is part of the serverless databases and storage section of the serverless stack. Much of today’s internet communications data is dominated by mostly unstructured data, including email, videos, photos, audio files, and other items. You can’t easily store unstructured data in traditional relational databases. Object storage, a prime example of serverless storage, is a storage architecture that can handle large amounts of unstructured data. Efficiently storing and managing this unprecedented volume of data is becoming a more crucial task every year, and object storage offers scalability that’s unavailable using traditional block or file storage. Here’s how object storage works. Objects are discrete units of data. Object storage does not have a hierarchy like a directory system; instead, each object is a self-contained repository that contains the data, metadata, and a unique identifier that applications use to access the object. These self-contained repositories result in a flat structure that is highly scalable in comparison to relational databases. The next ring in the serverless stack is **event streaming and messaging**. Serverless architectures are well-suited for event-driven and stream-processing workloads, which involves message queue integration, most notably Apache Kafka. Microservices need to communicate with each other, which often occurs using messaging queues. Having functions that can respond to new events or messages is crucial for a robust serverless architecture. The final attribute of the serverless stack consists of **API gateways**. API gateways act as proxies to web actions and provide HTTP method routing, client ID and secrets, rate limits, and more. In other words, HTTP events often trigger functions. For instance, a POST request to the endpoint for a function might trigger the function to perform a specific action. An API gateway can expose the HTTP method route so that the API is accessible to other services. In this video, you learned that: serverless is a set of attributes and not a single technology, FaaS exists as the core compute and processing engine for most serverless architectures, serverless storage is ready-made for the internet age, and messaging and API gateways provide crucial capabilities for a robust serverless application.

## Comparing the FaaS Model

Welcome to “Comparing the FaaS Model” After watching this video, you will be able to: Identify the benefits and drawbacks of Function-as-a-Service, or FaaS, compared to Platform-as-a-Service, known as PaaS, containers, and virtual machines. FaaS is the most central and most definitional element of the serverless stack. But other compute models play a role in serverless architectures too, so it’s worth exploring how FaaS differs from other common models of compute on the market today, across key attributes. The three main models to compare are platform-as-a-service, containers, and virtual machines. Function-as-a-service boasts an incredibly short provisioning time, in the range of milliseconds. Other compute models cannot rival this provisioning time, often because they require the provisioning of infrastructure. Other models require minutes or even hours. Containers, for example, can spin up very quickly, but an environment is needed to run that container. Provisioning a server or a virtual machine on which the container can run takes more time. Similarly, for virtual machines, applications need to install dependencies and be built in order to run. In addition, provisioning the virtual machine can take considerable time depending on the circumstances. Another characteristic of a compute model is administration. Function-as-a-service requires no administration because infrastructure is abstracted away by cloud providers. But other models require varying amounts of ongoing administration. While this administration is easy for platform-as-a-service, administration becomes more difficult for containers, and virtual machines require significant administration. Greater administration gives you greater controls, but greater administration also requires a lot of time and effort. Elastic scaling is a major component of FaaS, so clearly, this is an advantage for functions. Each action is always instantly and inherently scaled in response to demand. Other models also offer comprehensive, automatic, elastic scaling. The difference is that these models require careful tuning of auto-scaling rules. For example, since other models are less flexible than the pay-per-use model of FaaS, overprovisioning during auto-scaling can result in large, unexpected cost increases. Therefore, rules about the conditions and limits of scaling need to be carefully defined to prevent surprises. FaaS does not require capacity planning. However, other models require a mix of some automated scaling and some capacity planning. For containers, some auto-scaling rules can be created, but capacity planning is necessary to determine the amount of infrastructure on which the containers will run. All maintenance is managed by FaaS providers, and this is also true for PaaS. However, containers and VMs require significant maintenance, including updating and managing operating system, container images, connections, and more. High availability is inherent in the FaaS model without requiring any extra cost or effort. For other models, extra cost and effort is needed for high availability. Again, this is largely due to the burden taken on by the FaaS provider, whereas with other compute models, users need to implement high availability strategies themselves. For virtual machines, this might involve provisioning additional virtual machines in other data centers to be resilient against failures. Because resources are only invoked upon request, resources are never idle in the FaaS model. All other models, however, feature at least some degree of idle capacity. Other models do not feature the scale to zero capabilities that lets FaaS incur costs only when the function is invoked. FaaS is also incredibly flexible when it comes to the granularity of its billing model. FaaS charges per block of 100 milliseconds, which means you only pay for what you use, and not a second more. Other models tend to charge by the minute, or perhaps by the hour. In this video, you learned that: FaaS compares very well against other compute models, with millisecond provisioning time and no administration Provisioning time and amount of ongoing maintenance increase in this order: FaaS, PaaS, containers, virtual machines, Scaling and capacity planning are somewhat automated for models other than FaaS but do require tuning, Compute models other than FaaS can give greater flexibility but require more cost and effort.

## Serverless Reference Architecture and Use Cases

Welcome to “Serverless Reference Architecture and Use Cases” After watching this video, you will be able to: Describe how serverless supports a microservices architecture, identify key serverless use cases for data processing, massively parallel compute, and stream processing workloads. The most common use for serverless today is to support microservices architectures. The microservices model focuses on creating small services such that each service performs one job. Those services communicate with each other using APIs. While you can use either PaaS or Containers to build and operate microservices, serverless easily plugs into the single-task microservices architectural model. Also, serverless provides inherent and rapid provisioning, automatic scaling, and a pricing model that never charges for idle capacity. `Use cases` especially suited for serverless include **data processing**, **massively parallel compute**, and **stream processing**. Serverless is well-suited to working with structured text, audio, image, and video data—including transcoding videos to play on multiple device types, PDF processing, thumbnail generation, and image object character recognition, commonly referred to as OCR. OCR is taking an image of text, such as a scanned receipt—and converting the image into machine-encoded searchable, editable text. Consider again the scenario where you upload a profile picture to a website. The website might also require a thumbnail of that image for display on specific web pages. When a user uploads a photo to the site, this image is uploaded to an object storage bucket. This event triggers an IBM Cloud function that takes uses the uploaded image and creates the thumbnail image. The function also stores the thumbnail image in object storage so that when needed, the website can access the thumbnail image. Processing the image for other purposes, including facial recognition, is also possible. Any kind of parallel task is very well-suited for serverless runtime. Each parallelizable task results in one action invocation. Serverless is ideal for: **MapReduce** operations, **Web scraping**, **Monte Carlo simulations**, **Genome processing**. Serverless can even combine a parallelization use case with a data processing use case. For example, you saw how functions work to capture images for use on the Web. In this instance, a data processing use case with a parallel processing use case. The serverless function generates thumbnail images and creates those thumbnail images scaled quickly and in parallel. In another example, let’s say that a collection of 10,000 museum images are stored in object storage. If you want to generate thumbnails for each image, this scenario is incredibly well-suited for serverless for several reasons. First, this scenario is likely a one-time or sporadic occurrence, so continually running an application to do this doesn’t make sense. Furthermore, an action can handle each thumbnail generation. Monte Carlo simulations are mathematical methods that have been around for more than a century; and are used to estimate certain hard-to-predict future outcomes. Monte Carlo simulations are perfect for a broad range of scenarios, from weather forecasts to complex financial predictions. The displayed example attempts to predict stock prices for a specified number of days. The predict function runs several forecasts, each forecast predicting a specific number of days, and the Combine function summarizes the results. Since Monte Carlo simulations benefit from more sampling, running multiple forecasts improves the model. Each forecast runs as an independent function invocation, which accelerates the process. Combining managed Apache Kafka with FaaS and database and object storage offers a robust foundation for real-time buildouts of data pipelines and streaming apps. These architectures are ideal for working with all sorts of data stream ingestions for validation, cleansing, enrichment, and transformation. Applications of this use case include **IoT sensor data**, **log data**, and **financial market data**. Most internet of things devices generate data that needs to be processed. For example, a smart speaker in your home listens for verbal commands and takes actions accordingly. In this example, the processing of the user’s audio and the execution of any needed function can handle any required actions. When a user speaks, and the speaker captures the audio, that event triggers a function that uses verbal recognition software running in the cloud to analyze the request. Another function could also execute to perform the user’s requested action. In this video, you learned that: Serverless computing works well with microservices because services should perform a well-defined task and communicate via APIs. Serverless is effective for data processing, massively parallel compute operations, and stream processing workloads. 

## IBM Cloud Functions

Welcome to “IBM Cloud Functions” After watching this video, you will be able to: Define what IBM Cloud Functions are, List and describe the following eight IBM Cloud Functions: namespaces, actions, sequences, events, triggers, rules, feeds, and packages. IBM Cloud Functions are based on Apache OpenWhisk—a serverless, open-source platform. IBM Cloud Functions is a polyglot function-as-a-service programming platform for developing lightweight code that scales and runs on demand. Several components of this definition describe FaaS, such as scalability and on-demand performance. IBM Cloud Functions is also **polyglot, meaning that it supports numerous languages**. Next, learn more Cloud Function terminology. `Namespace` is an important term for Cloud Functions, so it’s valuable to understand this one first. **Namespaces contain other Cloud Functions entities**, such as actions and triggers, which you learn about soon. A Cloud Functions namespace is considered an “instance” within Cloud Functions, so access is granted at the namespace level, meaning that account admins can delegate access to a given namespace to other users. The fully qualified name of an entity is namespace ID slash package name slash entity name, because the namespace contains other entities. An `action` is a piece of code that performs one specific task. You can write an action in the language of your choice. An action performs work when directly invoked. A `trigger` enables an action to automatically respond to events from IBM Cloud services and third-party services. You provide your action to Cloud Functions either as source code or as a Docker image. You can use source code if your preferred language is supported. Supported languages include Node.js, Python, Swift, PHP, and others. You can use unsupported languages by creating a custom Docker image. A `sequence` is a chain of actions, invoked in order, where the output of one action is passed as input to the next action. Actions can be chained together into a sequence without having to write any code. By creating a sequence, you can combine existing actions for quick and easy reuse. A sequence can then be invoked just like an action, through a REST API or automatically in response to events. In this way, sequences are effectively just actions. Sequences are beneficial since it is a best practice for a function to perform a single action instead of multiple actions. Events from external and internal event sources are channeled through a trigger, and rules allow actions to react to these events. Examples of events include changes to database records, IoT sensor readings that exceed a specific temperature, new code commits to a GitHub repository, and simple HTTP requests from web-based or mobile apps. A trigger is a named channel for a class of events. A trigger is a declaration that you want to react to a certain type of event, whether from a user or by an event source. A `rule` associates a trigger with an action. Every time the trigger fires, the rule uses the trigger event as input and invokes the associated action. With the appropriate set of rules, a single trigger event can invoke multiple actions, or for a single action to be invoked as a response to events from multiple triggers. A `feed` is a convenient way to configure an external event source to fire trigger events that can be consumed by Cloud Functions. For example, a Git feed might fire a trigger event for every commit to a Git repository. A `package` is a bundle of feeds and actions. Integrations with services and event providers can be added with packages. An existing catalog of packages offers a quick way to enhance applications with useful capabilities and to access external services in the ecosystem. External services that have Cloud Functions packages include IBM Cloudant, Slack, and GitHub. For example, a trigger created with an IBM Cloudant change feed configures a service to fire the trigger every time a document is modified or added to an IBM Cloudant database. In this video, you learned that: IBM Cloud Functions is a FaaS service available on IBM Cloud. Namespaces are the overarching entity in which other Cloud Functions entities are stored. Events are channeled through triggers, and rules associate those triggers with the actions that should occur. Packages let you integrate applications with capabilities from external services.

## Module 2 Summary

- Serverless computing makes Infrastructure management for end users and enables developers to focus on their applications’ business-specific needs.
- Serverless code runs on-demand and scales transparently. On demand, pay-as-you-go server consumption means that organizations never pay for idle capacity.
- Serverless computing works well with microservices because services should perform a well-defined task and communicate via APIs. 
- Serverless is effective for data processing, massively parallel compute operations, and stream processing workloads.
- Serverless is well-suited for spiky workloads that can afford some latency, but long-running applications are better run using other platforms. However, serverless can lead to vendor lock-in and doesn’t always support every programming language.
- Function as a Service, known as FaaS, a subset of serverless computing, is an event-driven computing execution model and like serverless, FaaS is ideal for spiky workloads, with pay-as-you-go capabilities. Highly available, microservices compatible, FaaS applications consist of stateless, scalable, customized containers
- FaaS provides millisecond provisioning time and no administration. Compute models other than FaaScan give greater flexibility but require more cost and effort.
- IBM Cloud Functions is a FaaS service available on IBM Cloud. Within IBM Cloud, namespaces are the overarching entity where other Cloud Functions entities are stored. Packages let you integrate applications with capabilities from external services. Events are channeled through triggers, and rules associate those triggers with the actions that should occur.

## Glossary - Introduction to Serverless

[Click here](https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-CD0250EN-SkillsNetwork/cheatsheets/C9M2_Glossary_v1.1.pdf) to view and download "Introduction to Serverless" module glossary 

# ORM: MicroServices w/ Serverless

## Create and Invoke Actions - Part 1

Welcome to “Create and Invoke Actions Part 1” 
After watching this video, you will be able to: 
Describe how to create and invoke actions using IBM Cloud Functions. 
List the different modes for invoking actions. 
Describe how to retrieve the result of an action invocation. 
How do you create and invoke actions in Cloud Functions? 
For supported runtimes, source code can be provided directly to Cloud Functions. 
Since Node.js is supported, you can provide a JavaScript file. 
For example, this file named hello.js returns a JSON object with a payload of Hello world. 
To use source code from node.js to create an action, you can use the ibmcloud command 
line interface and the functions plugin. 
This command creates a function named hello using the hello.js file that you previously 
defined. 
You can list your functions by using the ibmcloud fn action list command. 
The output of this command displays your hello action under your account’s default namespace. 
Now that you created an action, you need to invoke the action so that it can perform its 
task. 
There are two modes for invoking actions: blocking invocations and non-blocking invocations. 
Blocking invocations invoke the action and waits for the result. 
This is accomplished by specifying the blocking flag on the command line. 
This is the “request and response” invocation style. 
You can also use a non-blocking invocation, which invokes the action immediately but does 
not wait for a response. 
Both block and non-blocking invocations always provide an activation ID that can be used 
to look up the action’s response, which is part of an activation record created by 
the platform. 
A blocking invocation request waits for the activation result to be available. 
The "hello” action can be invoked as a blocking activation with the action invoke 
command by including the blocking flag. 
This command outputs the activation ID so that the result can be reviewed at any time. 
This command outputs the complete activation record in JSON format. 
The activation record includes all information about the activation, including the function’s 
complete response. 
You can see the Hello world payload in the response. 
For the sake of space, this slide displays a truncated view of the activation record. 
No build step is required to run a function because the runtime is already deployed and 
waiting for function invocations. 
A non-blocking invocation immediately invokes the action and does not wait for a response. 
The invocation is accomplished using a similar command, but you do not include the dash dash 
blocking flag. 
Since the result is not awaited, you need retrieve the result later with the activation 
ID. 
The retrieve activation result command fetches only the result, which is the hello world 
payload. 
To retrieve the entire activation record, use the activation get command. 
Keeping track of the activation IDs can be challenging, and there are activation commands 
that can help. 
The activation get command run with the dash dash last flag retrieves the last activation 
record. 
You can also retrieve the last activation result by using the last flag with 
the activation result command. 
Finally, if you want to retrieve prior activation records or results, use the activation list 
command to list the most recent activations, which includes their IDs. 
In this video, you learned that: 
You can create Cloud Functions actions using source code, 
You can invoke Actions using either blocking or non-blocking invocations, 
Activation records are stored for each invocation and can be used to obtain the invocation’s 
response. 

## Create and Invoke Actions - Part 2

Welcome to “Create and Invoke Actions Part 2” 
After watching this video, you will be able: 
Invoke an action with parameters 
Bind default parameters to an action 
Call actions from actions 
Create and invoke sequence actions 
Functions can be more advanced than a simple “hello world.” 
Event parameters can be passed to an action when the action is invoked. 
A function can be updated to look for parameters. 
The input parameters are passed as a JSON object parameter to the main function. 
Notice how the name and place parameters are retrieved from the params object in 
this example. 
You can then apply the action update command. 
When invoking actions through the command line, parameter values can be explicitly passed 
using the param flag. 
In this case we invoke the hello action and pass Alex as the name parameter and IBM as 
the place parameter. Using the result flag performs a blocking invocation and outputs 
only the result and not the full activation record. 
This action makes the output more manageable. 
Use a JSON formatted file to pass parameters that include your required content. 
The filename must then be passed using the param-file flag. 
This parameters.json file declares the name and place as Alex and IBM. You can then invoke 
the action using the parameters from this JSON file. 
You can specify multiple parameters when you invoke actions—such as the name of a 
person and the place where they’re from. 
Rather than pass all these multiple parameters to an action every time, you can bind these 
parameters as default parameters. 
Default parameters are stored in the platform and automatically passed into the function 
as input during each invocation. 
If the invocation includes a parameter that has a default value, the passed value overrides 
the default parameter value. 
Parameters are bound when an action is created or updated. 
If you run the “action update” command and specify the place parameter, you define 
this value as the default. 
If this function is invoked and the place parameter is not explicitly provided, the 
function will use Earth as the default place, as seen in this example. 
Functions are modular and reusable, so you will often want to call one action from another 
action. Rather than having to manually construct HTTP requests to trigger actions, libraries 
pre-installed make requests easier. 
For example, you could create a proxy action that checks the password parameter and then 
calls another action if the password is correct. 
This code uses the Node package manager (NPM) Apache OpenWhisk JavaScript library, which 
is pre-installed in the Cloud Functions environment, so you don’t need to package the code. 
Invoking this proxy action with the incorrect password throws an error, while invoking the 
proxy action with the correct password will call your hello function. 
Sequence actions are created using a list of existing actions. 
When the sequence action is invoked, each action is executed in order of the action 
parameter list. 
Input parameters are passed to the first action in the sequence. 
Output from a function in the sequence is passed as the input to the next function and 
so on. 
The output from the last action in the sequence is returned as the response result. 
Sequences behave like normal actions—you can create, invoke, and manage them as actions. 
Providing the sequence flag to the action create command will create a sequence action. 
The sequence flag provides the actions in the order in which they will be executed. 
Since actions ought to perform a single task, creating modular actions lets them be reused 
in a variety of sequences. 
A funcs.js file defines three functions: 
First, the split function takes a single string and slices it into a JSON map of individual 
strings using a space as the delimiter. 
Note that the “action create” command assumes the function is named 
main. 
However, you can also use the main flag to specify the function name. 
Next, the reverse function takes a JSON array of strings and transposes the characters in 
each string. 
The third and final function is the join function. 
The join function takes a JSON array of strings and concatenates the array into a space-delimited 
string. 
On this slide, you can assume that the action is created using each of these functions. 
You can create a sequence of actions using the “action create” command and the sequence 
flag as shown here. Use the “action invoke” command invoke the sequence. 
But what does each step of this sequence look like? 
First, the “hello world” string is passed to the split action. 
The split command slices the string into two words and outputs as the result as a map that 
includes those two words. 
These outputs are passed as input to the reverse action, which reverses the characters in each 
word and outputs a map that includes both of those reversed words. 
Finally, the output of reverse action is passed into the join action, which then joins those 
reversed words into a single string. 
This new string is the output of the entire sequence. 
In this video, you learned that: 
Parameters can be passed to actions and given default values 
Actions can call other actions by using a pre-installed OpenWhisk library 
Sequences are a type of action and are created by chaining together existing actions 

## Manage Action with Packages

Welcome to “Manage Actions with Packages” 
After watching this video, you will be able to: 
Use packages provided by IBM Cloud Functions, 
Create, use, and share your packages, 
IBM Cloud Functions is pre-installed with public packages. 
Public packages include trigger feeds used to register triggers with event sources. 
Public packages also include actions, which anyone can use. Use the package list command 
to display the packages available in a specific namespace. 
The commands displayed onscreen here list the packages available in the whisk.system 
namespace. 
The package “get” command lists the entities present in a package. 
Here you see a portion of the output for the Cloudant package. 
Note that the package itself defines parameters that, if bound with values, can be used automatically 
by all actions in the package. 
This onscreen package includes the host and dbname to identify the database instance. 
The package also contains authentication parameters, such as the username and password, that all 
actions will need to access the database. 
If an application uses a single database, setting these values at the package level 
is helpful since all actions will authenticate the same way. 
The package also contains several actions, like creating and reading documents, and a 
feed named “changes.” 
All of the entities inherit parameters from the package. For example, the username and 
password don’t need to be passed to every invocation. 
The feed is a special action that monitors a specified Cloudant instance and fires causes 
triggers whenever you make changes to documents, allowing actions to react and perform work. 
To view the list of known parameters of an entity belonging to a package, you will need 
to run a get command with the summary flag. 
This command gets a description of the read document action. Here, you can see five parameters 
for this action. 
Three of these parameters—apihost, bluemixServiceName, and dbname—can be predefined at the package 
level and when invoked, the package inherits the predefined parameter values. 
As a result, the invocation only requires the document id parameter. 
Any entity listed under a package inherits specific bound parameters from the package. 
You can invoke actions in a package, just as with other actions. 
The next few steps show how to invoke the greeting action in the whisk.system samples package with 
different parameters. 
Getting a description of the greeting action shows that it takes two parameters: name and 
place. 
If you invoke the action without parameters, a generic message using default values is 
displayed. 
Of course, you can pass parameters to create a custom greeting. 
Although you can use the entities in a package directly, you might find yourself passing 
the same parameters to the action every time. 
You can avoid this situation by using the package bind command and specifying default 
parameters. 
The actions in the package inherit these parameters. 
You can bind to the samples package and set USA as the default place parameter. 
If you then get this package, you’ll see that all the samples' actions are available. 
If you then invoke the greeting action from the usaSamples package and do not provide 
the “place” parameter, the package uses default value of “USA.” 
You can create a custom package by applying the package create command to group your actions, 
manage default parameters, and share entities with other users. 
When you run the package get command with the summary flag, you’ll see that the package 
is empty. 
The identity.js file contains action code that returns all the input parameters. 
Use this code to create an action in the custom package using the action create command. 
You must prefix the package name to the action name. Getting a summary of the package now 
shows the new action. 
You can set default parameters for all the entities in a package. 
You do this by setting package level parameters that are inherited by all actions in the package. 
You can update the custom package to include two parameters: city and country. 
Invoking the identity action will now return the default city and country. 
After the actions and feeds that comprise a package are debugged and tested, you can 
share the package with all Cloud Functions users. 
Sharing the package enables other users to bind the package, invoke actions in the package, 
and author their own rules and sequence actions. 
Share the package by passing the shared flag and specifying yes to the update command. 
In this video, you learned that: 
IBM Cloud Functions provides packages that you can use and bind to specify default parameters, 
You can create your packages to group your actions, manage default parameters, and share 
entities with other users. 

## Connect Actions to Event Sources

Welcome to “Connect Actions to Event Sources” 
After watching this video, you will be able to: 
Identify and describe a trigger, 
Identify and describe a rule, 
Create a trigger and a rule that causes the trigger to invoke an action, and 
disable a rule. 
Before you connect actions to event sources, you need to understand triggers and rules, 
A trigger is a named channel for a class of event. 
You can use a dictionary of key-value pairs to activate or fire triggers. 
A user or an external event source can fire a trigger event. 
Each trigger event fired results in an activation ID. 
A feed is a way to configure an external event source to fire multiple triggers events that 
can be consumed by Cloud Functions. 
A rule associates one trigger with one action. 
Every firing of the trigger causes the corresponding action to be invoked with the trigger event 
as input. Imagine a system with two actions, classifyImage and thumbnailImage. 
There are also two triggers, newTweet and uploadImage. 
You can set rules so that the newTweet trigger invokes the classifyImage action, and the 
uploadImage trigger invokes both the classifyImage and the thumbnailImage actions. 
By enabling these rules, images in new tweets are classified, and uploaded images are both 
classified and thumbnailed. 
You can create a trigger to send location updates using the trigger create command. 
This trigger will fire when a location is updated. 
Use the trigger list command to verify that the trigger was created. 
The locationUpdate trigger is present in the output since the trigger was created previously. 
Then, use the trigger fire command using the provided parameters. 
For now, you’ll only see a confirmation. 
Currently, events fired to the locationUpdate trigger don’t do anything. 
You must create a rule to associate the trigger with an action. 
Assume that an action which displays a greeting is already created. 
You can hook up your newly created trigger to invoke that action. 
The create rule command requires three options: the name of the rule, the trigger, and the 
action. 
Getting the rule shows the trigger and the action bound by this rule. 
Now that the rule is set up for the locationUpdate trigger to fire the hello action, you can 
test the rule. 
First, you’ll fire the trigger. 
Remember that each time you fire the locationUpdate trigger with parameters, the hello action 
will be called with those parameters. 
Next, you can verify that the action was invoked by checking the activations list. 
Not only is the action recorded, but the trigger is recorded as well. 
Then, you can then use the action’s activation ID to view its result and verify that the 
correct payload was returned. 
Rules are automatically enabled when created. 
Rule can be disabled and re-enabled via the command line. 
Apply the rule disable command to prevent the associated trigger from invoking the associated 
action. 
In this video, you learned that: 
A rule associates one trigger with one action. 
Rules cause actions to be invoked when the associated trigger is fired. 
Using multiple rules can cause a trigger to invoke multiple actions or an action to be 
invoked by multiple triggers. 

## Expose Actions as APIs

Welcome to “Expose Actions as APIs.” 
After watching this video, you will be able to: 
Describe why you need to expose actions as APIs, 
Create a web action, 
Identify the benefits of web actions, 
Identify the benefits of using the API Gateway service, and 
describe how IBM Cloud Functions work with an integrated API Gateway. 
Initially, an action is only usable from the command line interface using the invoke command 
or the web console. 
Web apps can’t easily invoke actions using these two methods. 
For a web app to call the action directly, you must expose the action as a web action 
via a RESTful API so that other services can call those actions. 
In a production microservices application that uses Cloud Functions, functions need 
to be directly accessible without using the command line interface. 
And Microservices often communicate via HTTP requests. 
Fortunately, using Cloud Functions, you can turn actions into web actions invoked using 
HTTP so that services can easily invoke these web actions within a microservices architecture. 
When using Cloud Functions, when you can annotate new actions using the web true flag to convert 
those actions into web actions. 
The result is the creation of a public URL that can trigger the action from any web app. 
Web actions can then be invoked via HTTP requests without user authentication. 
The HTTP request parameters are automatically converted into event parameters. 
Web actions can control the HTTP response headers and body to support content types 
directly, manage cookies, and perform HTTP redirects. 
Web actions provide many benefits. 
First, web actions can be invoked from anywhere without defining a trigger or a rule. 
Some serverless functions are only invoked due to an event, and thus a trigger is important. 
However, web apps might want to directly invoke actions. 
Secondly, You can access web actions through a REST interface without credentials. 
Next, web actions support all content types on an HTTP response so that functions can 
return HTML, XML, SVG, PNG, and others, with intelligent defaults for JSON. 
Finally, web actions support any HTTP method, including GET, POST (which is the default), 
PUT, PATCH, and DELETE, as well as HEAD and OPTIONS. 
You can easily create a web action by passing the web flag with the value of true. 
If you already created an action, you can update the existing action and pass this same 
web flag. 
To use a web action, you need its public URL. 
You can retrieve the public URL by using the action get command and passing the hello URL 
flag. 
In addition to creating web actions, Cloud Functions also provides an integrated API 
Gateway service. 
You can use the Integrated API service to create new HTTP APIs that map incoming requests 
to actions based on the path or the HTTP method. 
This capability lets you have a single API path that responds to both GET and POST requests. 
The API Gateway service then routes the HTTP requests to the appropriate web actions depending 
on the path or method. 
The API Gateway service also can perform user authentication, rate limiting, and more. 
You do not need to implement these capabilities within your web actions. 
To use the API Gateway, you’ll need to apply API subcommands. 
The subcommand to create an API is ibmcloud fn api create base path API name HTTP method 
action name. 
The pathname for an API extends the base path, if the base path is provided. 
Although the base path is not required, specifying a base path can help you logically group APIs. 
All actions used in an API must be web actions. 
In the labs, you’ll have more chances to use web actions and APIs. 
In this video, you learned that: 
Web actions create a public URL that you can use to invoke an action rather than using 
triggers and rules. 
After creating a web action, you can use the Cloud Functions integrated API Gateway to 
expose web actions via an API. 
The API Gateway performs robust API management on your behalf, such as routing and rate limiting. 

## Module 3 Summary

Congratulations! You have completed this module. At this point in the course, you know that:

You can create Cloud Functions actions using source code

Actions can pass parameters and apply default values​. Actions can call other actions by using a pre-installed OpenWhisk library​. Sequences are a type of action and are created by chaining together existing actions. You can invoke actions using either blocking or non-blocking invocations. Activation records are stored for each invocation and you can use the activation record to obtain the invocation’s response

IBM Cloud Functions provides packages that you can use and bind to specify default parameters. You can create packages to group your actions, manage default parameters, and share entities with other users.

A rule associates one trigger with one action. When the associated trigger is fired, rules invoke actions. Using multiple rules can cause a trigger to invoke multiple actions or an action to be invoked by multiple triggers 

Web actions create a public URL that you can use to invoke an action rather than using triggers and rules. After creating a web action, you can use the Cloud Functions integrated API Gateway to expose web actions via an API.

You can use the API Gateway to perform robust API management on your behalf, such as routing and rate limiting.

## Glossary - ORM: MicroServices w/ Serverless

[Click here](https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-CD0250EN-SkillsNetwork/cheatsheets/C9M3%20Glossary%20v1.3.pdf) to view and download "ORM: MicroServices w/ Serverless" module glossary 

# OpenShift Essentials/Working with OpenShift and Istio

## OpenShift Recap

Welcome to the “Red Hat OpenShift Recap.” 
After watching this video, you will be able to: 
Explain what Red Hat OpenShift is, 
Describe the relationship between OpenShift and Kubernetes, and 
identify the services provided by OpenShift to facilitate operations and development tasks. 
The concise definition of OpenShift, as provided on the Red Hat website, says that OpenShift 
is a hybrid cloud, enterprise Kubernetes application platform. 
Hybrid cloud is an IT architecture that incorporates workload portability, orchestration, and management 
across premises and cloud environments. 
You can run OpenShift in both on-premises and cloud environments. 
OpenShift builds on open-source Kubernetes to create an application platform. 
As an application platform, OpenShift does more than orchestrate containers. 
OpenShift also provides additional tooling around the complete lifecycle of applications—from 
build and CI/CD—to monitoring and logging. 
Of course, we should note that OpenShift is developed and supported by Red Hat. 
OpenShift is a platform for running microservices. 
OpenShift is tailormade for deploying cloud-native services in an automated fashion. 
Serverless architectures often work in tandem with other forms of compute such as virtual 
machines and containers. 
OpenShift orchestrates containerized workloads and thus provides an excellent pattern for 
a cloud-native application. 
You can integrate OpenShift with serverless technologies when serverless can better meet 
your organization’s needs. 
Kubernetes and OpenShift are closely connected. 
An analogy to the Linux kernel is often used to convey the relationship between Kubernetes 
and OpenShift. 
A kernel is a powerful program at the center of an operating system. 
While the Linus kernel is foundational and capable, many Linux distributions, such as 
Ubuntu, Fedora, and Debian, build upon the kernel. 
These distributions are operating systems with additional features and functions that 
use the Linux kernel as their own. 
Just like a Fedora distribution of Linux, OpenShift is a distribution of Kubernetes, 
building on its foundational capabilities. 
Let’s look at what’s included with OpenShift using a diagram reproduced from the OpenShift 
website. 
First, in an OpenShift environment, the Kubernetes master runs on Red Hat Enterprise Linux CoreOS, 
while the worker nodes support Red Hat Enterprise Linux. 
Next is Kubernetes. 
As we’ve already mentioned, Kubernetes is an integral part of OpenShift, part of the 
offering. 
So far, the OpenShift architecture is like Kubernetes. 
OpenShift infrastructure includes Kubernetes deployed on top. 
Next are cluster services. 
Cluster services include integrated monitoring, a private registry deployed within the cluster, 
networking solutions, and many other features designed to create a helpful and intuitive 
user experience. 
On top of the cluster services, platform services help users manage their workloads. 
Application services help users build cloud-native apps, while developer services help increase 
developer productivity. 
In this video, you learned that: 
Red Hat OpenShift is a platform for running containerized workloads like microservices. 
OpenShift is like a Kubernetes distribution in that OpenShift builds additional capabilities 
on top of Kubernetes. 
OpenShift provides a variety of services to manage workloads, build cloud-native apps, 
and increase developer productivity. 

## Service Mesh and Istio

Welcome to “Service Mesh and Istio.” 
After watching this video, you will be able to: 
List the benefits of microservices, 
Describe the challenges that come with microservices, 
Explain what a service mesh is, 
Describe why a service mesh is useful, 
Describe how a service mesh can alleviate common microservices challenges. 
Using a microservices architecture to build cloud-native applications provides numerous 
benefits. 
Updating code is more manageable with microservices—you 
only need to update the relevant services. 
With microservices, teams who develop different application components are free to use other 
technology stacks that meet their unique needs. 
In addition, when an application is running, components 
that experience more load can be scaled independently, 
preventing the entire application from needing to be scaled when only one component requires 
more resources. 
Using microservices also brings some challenges. 
Microservices require configuration to secure communications and set up encryption. 
Development teams might want to roll out new features to a subset of users or compare two 
versions of a new feature to see which version most engages users. 
In these situations, teams need canary deployments and A/B testing. 
Communication between microservices also leads to the possibility of cascading failures if 
one service is unreachable or particularly slow. 
To prevent communication failures from cascading to multiple microservices, developers must 
implement retries and circuit breaking. 
Now let’s talk about service meshes. 
A service mesh is a dedicated layer for making service-to-service communication secure and 
reliable. 
Among other capabilities, service meshes provide traffic management to control the flow of 
traffic between services, security to encrypt traffic between services, and observability 
of service behavior to troubleshoot and optimize applications. 
To learn more about service mesh capabilities, and specifically the Istio service mesh, here 
is Ram Vennam from the IBM Cloud team. 
Let's use this example application. 
I have a UI microservice talking to two versions of catalog, which talk to inventory. 
All of these are services deployed inside of a Kubernetes cluster. 
The number one reason why someone uses a service mesh 
is because they want to secure their workload. 
So they want mutual TLS when one service is talking to another. 
Next, they want to dynamically configure how the services are connected to one another. 
So, in this example, there's version one and version two. 
So, I might want to send 90 percent of the traffic to version 1 and then 10 percent 
of the traffic to version 2 while I do testing and incremental rollouts. 
I might also want to try adding retry policies and circuit breaking to harden my system. 
Three. I want to observe how my application is doing end to end, not just if a service is up 
or down but see where the bottlenecks are in the system and how traffic is flowing. 
And four, I want to control who has access to talk to what. 
In this example, UI is allowed to talk to catalog, and catalog is allowed to talk to inventory, 
but UI is not allowed to talk to inventory directly, 
and rogue containers cannot talk to inventory service. 
You can get more granular than that and say that UI is allowed to make an HTTP get request 
and catalog is allowed to make a post request to inventory. 
In the past, we used to have our developers program all of these 
features directly into their application code. 
That slowed down the dev cycle, it made these microservices bigger, and just generally made 
everything less flexible, but now there's a better way and that's the service mesh. 
You keep your application small and business-focused and, instead, 
you dynamically program the intelligence into the network and that's exactly what Istio does. 
So, when you have Istio installed, the first thing you'll do is... it'll automatically inject proxies 
next to each one of your containers, and these proxies are envoy proxies, 
and the proxy itself runs in a container next to your application container, 
but it runs inside the same Kubernetes pod. 
Now, when UI wants to talk to catalog, the proxy will actually intercept that request, 
apply any policies, and then route traffic to the proxy on the other side, 
and then the catalog proxy will receive that request and then forward it down to the catalog. 
Istio will configure each one of these proxies with your desired configuration. 
Istio extends Kubernetes using CRDs. 
So, to apply Istio configuration, you just write your YAML and then apply it to Kubernetes. 
The Istio galley component will receive that YAML, validate it, and then hand it over to Istio pilot. 
Pilot will convert that configuration to envoy configuration 
and distribute it to each one of the proxies. 
If you want the proxies to add additional policies and rules there's a policy component. 
And then these proxies constantly report telemetry information about 
what's going on into your system to the Istio telemetry component. 
And last but not least, there's citadel. 
Citadel is responsible for providing a strong identity 
to each one of the services in your system. 
It also generates certificates and rolls it out to each one of the proxies 
so that the proxies can do mutual TLS when they're talking to one another. 
To get started with Istio and to configure Istio, 
there's three main resources that you need to learn about. 
First, there's a gateway. 
Gateway is like a load balancer that sits at the 
edge of your mesh and accepts incoming and outgoing HTTP and TCP connections. 
Next, to direct traffic from gateway to your services you create a virtual service. 
And a virtual service can be bound to a gateway and direct traffic to UI 
or it could be bound to a service and then direct traffic to your other services, 
where you can apply policies like ninety percent and ten percent traffic split rules. 
Once traffic is routed, you can apply rules on top of that traffic 
such as TLS settings or circuit breaking, and those are done using destination rules. 
And those are the three main resources you need to know about Istio. 
I'm actually going to put policy and telemetry in asterisks because 
there's some refactoring that's going on with these components. 
The logic is being moved outside of this control plane 
and into the proxies themselves to avoid the additional network hop. 
This translates to improved performance. 
In this video, you learned that: 
Microservices architectures need security between 
services as well as ways to manage and test services, 
A service mesh is a dedicated layer that provides 
security and more by coordinating communication in the environment, 
Istio provides traffic shifting, mutual transport layer security, 
and telemetry when deployed with microservices.

## Microservices with OpenShift

Welcome to Microservices with OpenShift. 
After watching this video, you'll be able to 
Describe how OpenShift makes developers lives easier, 
Explain the process by which microservices are deployed on OpenShift. 
Watch Si Vennam from the IBM Cloud team describe how to deploy microservices with OpenShift. 
We'll start with developers. 
So we'll sketch out a developer up here. 
Now what does a developer have to do? 
Well, they generally have to write applications, create changes, test them out, 
deploy them into a cluster, and they're really just focused on that 
and any other kind of distractions will slow them down from that task. 
So, with dev, the first thing that they're going to want to 
do when starting with OpenShift is to create a project and an application. 
To do so, OpenShift has two different ways of enabling developers to work with their platform. 
So, one you can take advantage of the CLI, 
and there's also a really powerful web console that they could work with as well. 
So, the first thing that the dev wants to do 
is take advantage of one of those two form factors to create a project and an application. 
And there's templates for all different kinds of source code 
and programming languages that the dev wants to work with. 
So, they'll go ahead and do that and then, 
you know, once they get into their flow of creating updates to an application, 
the very first step they're going to want to do is push changes to a repository. 
And in this case, let's use GitHub as an example. 
Let's say that this developer is making changes into GitHub. 
That's really all they need to do. 
Behind the scenes, OpenShift is going to take care of the rest. 
So, when that application and project was created, OpenShift in the back end will create a jenkins 
job and pipeline that helps power deploying this application. 
So, once code gets pushed into that GitHub, it'll trigger a web hook, which kicks off a Jenkins job. 
Which is just going to do two things: 
First, what it's going to do is do something called source to image, 
which is going to create a docker image out of that source code. 
Next, it's going to go ahead and take that and put it into a registry. 
A private registry, which comes built-in in OpenShift and, in fact, you can actually 
use public registries or your own registry if you have it outside of this context as well. 
Once that image gets built and pushed into that registry 
next, what OpenShift will do is go ahead and push that into the actual cluster. 
And that's what we've got here is two hosts that are in our cluster in OpenShift. 
We're gonna take that image and let's say that we've set it up to deploy two times. 
And we'll call this v1 of the application. 
So, let's kind of overview that process one more time. 
So, the developer makes some change to a code then Jenkins will kind of kick off that build, 
create an image, push that image to a registry, 
and then a little bit of a different thing here, 
So, in this step right here, OpenShift takes advantage of something called image streams, 
which is a little bit different to how Kubernetes will do things and essentially 
what it enables you to do is whenever a change is kind of detected with that image, 
an image stream will allow you to push those with no downtime to your applications. 
So, what it'll do is, you know, with that new version of that code, it'll bring down the old 
version, start the new version until we've rolled out the whole new version of that application. 
This is just a few ways that OpenShift makes developers' lives easier. 
In this video, you learned that OpenShift creates a Jenkins 
job to automatically build microservices into containers, 
OpenShift pushes the built containers to a registry 
and deploys those containers to the cluster 

## Red Hat Marketplace

Welcome to "Red Hat Marketplace." 
After watching this video, you will be able to: 
Explain why using third-party software with microservices is beneficial and 
Describe how Red Hat Marketplace solves the challenges of discovering, procuring, and 
managing software 
Developing and deploying microservices using OpenShift is a simple and streamlined process. 
In addition to developing your own microservices, OpenShift enables you to supplement your solutions 
using other third-party software. 
You'll likely use third-party software, including databases, logging and monitoring solutions, 
or any number of other options that can help make your application more robust. 
Third-party software can be a great way to fill gaps without having to develop entire 
solutions yourself. 
But when it comes to choosing third-party software, a lot of questions arise. 
How can you discover software certified to work in your environment? 
How can you purchase that software? 
How can you deploy that software? 
And, after deployment, how can you manage ongoing tasks such as updates? 
Red Mat Marketplace solves each of these concerns. 
According to its website, Red Hat Marketplace is "a simpler way to try, buy, and manage 
certified software for Red Hat OpenShift." 
How does it work? 
Red Hat Marketplace provides a one-stop-shop for software certified to run on Red Hat OpenShift. 
You can search for available products and filter the results based on multiple categories. 
Each product includes information about the software's automation capabilities, such as 
whether the software performs installations, seamless upgrades, and other software lifecycle 
tasks. 
Red Hat Marketplace enables you to size software to your needs, sign up for free trials, and 
purchase your software. 
The Marketplace provides real-time pricing, billing, and subscription choices, and multiple 
payment options. 
You can quickly deploy your purchased software automatically via Red Hat Marketplace to selected 
OpenShift clusters on any cloud or on-premises environment. 
Finally, you can use Red Hat Marketplace to perform many lifecycle actions, such as seamless 
upgrades and deep insights like metrics, alerts, log processing, and workload analysis. 
Red Hat provides continuous support for all products purchased through the Marketplace. 
Next, watch Rojan Jose from the IBM Cloud team demonstrate how to find a database solution 
on the Red Hat Marketplace. 
Let's say as a developer, I'm looking for database progress. 
Click on the database category to see the complete list of database products. 
Use the filter on the left to narrow down the results. 
Click on the product title to view product details. 
I'm going to open MemSQL. 
As you can see, MemSQL meets certification standards on 5 different parameters. 
It also supports Phase 1 and Phase 2 on the Operator maturity model. 
The overview tab provides general information about the product and reviews from G2. 
Reviews from a third-party source allows the marketplace to be rendered neutral. 
The documentation tab provides links to getting started and installation guides. 
The pricing tab offers a summary of product pricing by tiers 
Product entitlement can be based on the number of containers, user account, application and 
instances, etc, along with a subscription which can be monthly or yearly renewals. 
Metering best usage and managing overages will be made available in future releases. 
And the Help tab gives you more information about the support plan. 
In this video, you learned that: 
Certified software fills gaps in your application, eliminating the need for your organization 
to develop new microservices, and 
Red Hat Marketplace provides a central location to try, buy, deploy and manage software certified 
for OpenShift environments 

## Module 4 Summary

Congratulations! You have completed this module. At this point in the course, you know that: 

Red Hat OpenShift is a platform for running containerized workloads like microservices. 

OpenShift is like a Kubernetes distribution in that OpenShift with additional capabilities. OpenShift services help manage workloads, build cloud-native apps, and increase developer productivity. For example, OpenShift creates a Jenkins job to automatically build microservices into containers. In addition, OpenShift pushes the built containers to a registry and deploys those containers to the cluster 

Microservices architectures need security among services as well as ways to manage and test services. 

A service mesh is a dedicated layer that provides security and more by coordinating communication. Istio is a service mesh that provides traffic shifting, mutual transport layer security, and telemetry when deployed with microservices.  

Certified software fills development gaps in your application, eliminating the need for your organization to spend the time and money  to develop new microservices. Red Hat Marketplace provides a central location to try, buy, deploy and manage software certified for OpenShift environments. 


## Glossary - OpenShift Essentials/Working with OpenShift and Istio

[Click here](https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-CD0250EN-SkillsNetwork/cheatsheets/C9M4%20Glossary%20v1.1.pdf) to view and download " OpenShift Essentials/Working with OpenShift and Istio" module glossary 

# Final Project