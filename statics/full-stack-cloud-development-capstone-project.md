[<=](../index.md) |
[Course content online]()
___

- [Static page](#static-page)
  - [Introduction to Capstone Project](#introduction-to-capstone-project)
  - [Static Pages](#static-pages)
- [User management and CI/CD](#user-management-and-cicd)
  - [User Management Overview](#user-management-overview)
  - [CI/CD Overview](#cicd-overview)
- [Backend services](#backend-services)
  - [Back End Services Overview](#back-end-services-overview)
  - [Django Models Views](#django-models-views)
- [Dynamic pages](#dynamic-pages)
  - [Dynamic Pages Overview](#dynamic-pages-overview)
- [Containerize \& Deploy to Kubernetes](#containerize--deploy-to-kubernetes)
  - [Overview](#overview)
  - [Add Dockerfile](#add-dockerfile)
  - [Push built image to container registry](#push-built-image-to-container-registry)
  - [Add deployment artifacts](#add-deployment-artifacts)
  - [Deploy the application](#deploy-the-application)
- [Assignments](#assignments)
  - [URLs](#urls)
  - [Screenshots](#screenshots)

# Static page
## Introduction to Capstone Project

**Estimated time needed: 9-11 hours**

A national car dealership with local branches spread across the United States recently conducted a market survey. One of the suggestions that emerged from the survey was that customers would find it beneficial if they could access a central database of dealership reviews across the country.

You are a new hire at the company. You are assigned the task of building a website that allows new and existing customers to look up different branches by state and look at customer reviews of the various branches. Customers should be able to create an account and add their review for any of the branches. The management hopes this will bring transparency to the system and also increase the trust customers have in the dealership.

After thorough research and brainstorming, the team developed use cases for anonymous, authorized, and admin users.

**Use cases for anonymous users:**

- View the "Contact Us" page.
- View the "About Us" page.
- View the list of dealerships.
- Filter the list of dealerships by state.
- Click on a dealership to view the reviews for that dealership on the details page.
- Log in using their credentials.

**Use cases for authorized users:**

In addition to the above, authorized users should be able to write a review for any dealership on the dealership's page. In order to enable authorized users to write their reviews:

- A Review button should be provided against each dealer listed in the dealership table.
- Clicking on the Review button should take the user to the review page.
- Filling the form on the review page and submitting it should add the review. 

```
{ "user_id": 1, "name": "Berkly Shepley", => from Django "dealership": 15, => from the form "review": "Total grid-enabled service-desk", => form textbox "time": "", => current time "purchase": true, => form checkbox "purchase_date": "07/11/2020", => form calendar (bootstrap) "car_make": "Audi", => from django dropdown "car_model": "A6", => from django dropdown "car_year": 2010 => form django dropdown } 

```

On submission, user should be taken back to the dealership detail page with the submitted review featured at the top of the reviews list, sorted on time.

**Use cases for admin users:**

- Log in to the admin site with a predefined username and password.
- Add new make, model, and other attributes.

Your organization has assigned you as the Lead Cloud Application Developer on this project. Your job is to develop this portal as part of your Capstone project by following best practices for cloud application development.

Review Criteria – 100 marks total

The capstone project is divided into five modules. Each module has a quiz followed by a final submission that is graded by your peers in this course. The grading is divided as follows:

- Module 1 Checklist (10 points)
- Module 2 Checklist (8 points)
- Module 3 Checklist (10 points)
- Module 4 Checklist (6 points)
- Module 5 Checklist (6 points)
- Final Submission (60 points)

Next Steps

Be sure to read the capstone overview before starting with the step-by-step instructions.

- [Capstone Overview](./capstone-overview.pdf)
- [Capstone Prework](./capstone-prework.pdf)

## Static Pages

Congratulations on your new role as the lead software developer at the `Best Cars` dealership. As a warm-up task, you need to build and deploy an initial Django app on IBM Cloud.The Django app will be mainly used for user management and authentication, managing car models and makes, and routing other IBM cloud services for dealership and reviews. You will build this Django app and related cloud services incrementally along the capstone course.

In this learning module, you are asked to perform the following tasks:

- Fork Github repo containing the project template
- Create your own Github repo storing your project assets
- Add a navigation to the website using bootstrap
- Add a "about us" static page
- Add a "contact us" static page
- Run and test the Django application

Follow the instructional lab to complete above tasks step by step.

- [Add static pages](./static-pages.pdf)

# User management and CI/CD

## User Management Overview

Now, you have the initial Django application built and deployed. In the next step, the admins of the dealership will review the app to identify users and manage their accesses based on roles (such as anonymous users or registered users). Thus, you are planning to add authentication and uthorization, i.e., user management, to the app.

In this lesson, you need to perform the following tasks to add the user management feature:

- Create a super user for the Django admin site
- Add a user login/logout and signup menu items to the navigation bar in the Django template
- Add a Django login view to handle login request
- Add a Django logout view to handle logout request
- Add a Django signup template
- Add a Django signup view to handle signup request

Follow the instructional lab to complete the above tasks step by step.

- [User Management](./user-management.pdf)

## CI/CD Overview

Congratulations on running and testing the application. The next step is setting up Continuous Integration and Continuous Delivery for your source code. This is particularly important if you have multiple people working on the project. Continuous Integration provides a way for developers to collaborate and Continuous Delivery provides a way to deliver your changes to the clients without interruptions.

In this module you will:

- Create a toolchain service on IBM Cloud
- Create a CI/CD pipeline from your Github repository
- Enable code, build, and linting stages

Follow the instructional lab to complete the above tasks step by step.

- [Add Continuous Integration with Linting](./add-continuous-integration-with-linting.pdf)

# Backend services

## Back End Services Overview

The Django application you created in the last module needs to communicate with the database. In 
this module, you will create actions on IBM Cloud Functions and serve them behind an API 
endpoint.

You will build several actions in Python and JavaScript to perform database operations including:

- Get all dealerships
- Get all dealerships for a given state
- Get all reviews for a dealership
- Post a review for a dealership

Follow the instructional lab to complete above tasks step by step

- [Implement IBM Cloud Function Endpoints](./implement-ibm-cloud-function-endpoints.pdf)
- [Creating the API Endpoint URL’s using Actions on IBMCloud](./functions-endpoint.pdf)

## Django Models Views

Now that you have created dealership and views related CRUD cloud functions.  Next, we need to 
create data models and services for the dealers' inventory. Each dealer manages a car inventory 
with different car models and makes, which are, in fact, relatively static data, thus suitable to be 
stored in Django locally. 

To integrate external dealer and review data, you will need to call the cloud function APIs from the 
Django app and process the API results in Django views. Such Django views can be seen as proxy 
services to the end user because they fetch data from external resources per users' requests.

In this lesson, you need to perform the following tasks to add car model and make related models 
and views, and proxy services:

- Create CarModel and CarMake Django models
- Register CarModel and CarMake models with the admin site
- Create new car models objects with associated car makes and dealerships
- Create a `get_dealerships` Django view to get dealer list
- Create a Django `get_dealer_details` view to get reviews of a dealer
- Update the `get_dealer_details` view to call Watson NLU for analyzing review sentiment
- Create an `add_review` Django view to post dealer review

Follow the instructional lab to complete the above tasks step by step.

- [Build CarModel and CarMake Django Models](./build-carmodel-and-carmake-django-models.pdf)
- [Create Django Proxy Services Of Cloud Functions](./create-django-proxy-services-of-cloud-functions.pdf)

# Dynamic pages

## Dynamic Pages Overview

You created all necessary backend services (Django views and cloud functions) for managing dealerships, reviews, and cars in the last module. Next, it is time to create some stylized front-end Django templates to present those service results to the end users.

In this learning module, you need to perform the following tasks to add the front-end to the app:

- Create a dealership list template and update the dealership list view
- Create a dealer details/reviews template and update the dealership detail view
- Create a review submission page and add a submission view

Follow the instructional lab to complete above tasks step by step.

- [Add dynamic pages](./add-dynamic-pages.pdf)

# Containerize & Deploy to Kubernetes

## Overview

In line with the latest trends in technology and to avoid vendor lock-in, your management team is looking to deploy the dealership application to multiple clouds. The application is currently running on Code Engine, but you have been told not all cloud providers have a hosted Code Engine service. You are put in charge to look at containers as a possible way to mitigate this problem as all the big cloud providers have a way to host and manage containers. When containerizing an application, the process includes packaging an application with its relevant environment variables, configuration files, libraries, and software dependencies. The result is a container image that can then be run on a container platform. You are also asked to use Kubernetes to manage the containerized deployment. Kubernetes is an open-source container orchestration platform that automates the deployment, management, and scaling of applications.

In this module you will:
- add the ability to your application to run in a container
- add deployment artifacts for your application so it can be managed by Kubernetes

Follow the instructional lab to complete the above tasks step by step.

You have made good progress in your assignment thus far! Your Django application is running on IBM Cloud, and your team is happy. However, your boss has a new ask. The company is looking at using containers to manage and deploy the application. Furthermore, the management is interested in using the hybrid cloud strategy where some applications and services reside on a private cloud and others on a public cloud. To provide a more robust development experience, you are asked to look at Kubernetes. So, let’s containerize your application now.

**NOTE**: Before starting the lab, please follow the steps to check and delete previously persisting sessions to avoid any issues while running the lab.

- Please run the below command:

```sh
kubectl get deployments
```

- If you see that the `dealership` deployment already exists, please delete it using:

```sh
kubectl delete deployment dealership
```

- Please run the below command:

```sh
ibmcloud cr images
```

- If there is any `dealership` image, please delete it using:

```sh
ibmcloud cr image-rm us.icr.io/sn-labs-moj/dealership:latest && docker rmi us.icr.io/sn-labs-moj/dealership:latest
```

**Please enter your SN labs namespace in place of** `sn-labs-moj`

- If you do not remember your namesapce, you can get it by using either of the below commands:
  - oc project
  - ibmcloud cr namespaces (Please use the one which is of the format `sn-labs-$USERNAME)`
- Please sign out of SN labs & clear your browser cache and cookies.
- Please start the lab again & proceed as below.

## Add Dockerfile

Create a `Dockerfile` in the root directory. The file will have the following steps listed:

1. Add base image.
2. Add requirements.txt file.
3. Install and update Python.
4. Change working directory.
5. Expose port.
6. Run command to start application.

Here is an example file to get you started:

```docker
    FROM python:3.8.2

    ENV PYTHONBUFFERED 1
    ENV PYTHONWRITEBYTECODE 1

    RUN apt-get update \
        && apt-get install -y netcat

    ENV APP=/app

    # Change the workdir.
    WORKDIR $APP

    # Install the requirements
    COPY requirements.txt $APP
    RUN pip install --upgrade pip
    RUN pip install -r requirements.txt

    # Copy the rest of the files
    COPY . $APP

    EXPOSE 8000

    RUN chmod +x /app/entrypoint.sh
    ENTRYPOINT ["/app/entrypoint.sh"]

    CMD ["gunicorn", "--bind", ":8000", "--workers", "3", "djangobackend.wsgi"]
```

**Note**: Please ensure that the contents of the Dockerfile are indented as above

Notice that the the second to last command in Dockerfile refers to `entrypoint.sh`. This file should have the following content:

```bash
    #!/bin/sh

    if [ "$DATABASE" = "postgres" ]; then
        echo "Waiting for postgres..."

        while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
        sleep 0.1
        done

        echo "PostgreSQL started"
    fi

    # Make migrations and migrate the database.
    echo "Making migrations and migrating the database. "
    python manage.py makemigrations main --noinput 
    python manage.py migrate --noinput 
    exec "$@"
```

Please use the below command to make `entrypoint.sh` executable.

```bash
chmod +x ./entrypoint.sh
```

## Push built image to container registry

If you remember from the previous course in this certification, you were asked to build your image and push to IBM Cloud Image Registry (ICR). You need to do the same here and then refer to this image in your Kubernetes deployment file.

Please export your SN labs namespace as below:

```sh
export MY_NAMESPACE=sn-labs-moj
```

Note: Please enter your SN labs namespace in place of `sn-labs-moj`

```sh
docker build -t us.icr.io/$MY_NAMESPACE/dealership .
```

Next, push the image to the container registry:

```sh
docker push us.icr.io/$MY_NAMESPACE/dealership
```

## Add deployment artifacts

Create `deployment.yaml` file to create the deployment and the service. It should look something like:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    run: dealership
  name: dealership
spec:
  replicas: 1
  selector:
    matchLabels:
      run: dealership
  strategy:
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
    type: RollingUpdate
  template:
    metadata:
      labels:
        run: dealership
    spec:
      containers:
      - image: us.icr.io/sn-labs-moj/dealership:latest
        imagePullPolicy: Always
        name: dealership
        ports:
        - containerPort: 8000
          protocol: TCP
      restartPolicy: Always
  replicas: 1
```

## Deploy the application

Create the deployment using the following command and your deployment file:

```sh
kubectl apply -f deployment.yaml
```

Normally, we would add a service to our deployment, however, we are going to use port-forwarding in this environment to see the running application.

```sh
kubectl port-forward deployment.apps/dealership 8000:8000
```

**Note**: If you see any errors, please wait for some time & run the command again.

Click on the Skills Network button on the right, it will open the “Skills Network Toolbox”. Then click OTHER then Launch Application. From there you should be able to enter the port as 8000 and launch, to see the running application. You will get an error from the home page. Add /djangoapp at the end of the URL to see your application.

# Assignments

## URLs

1. Submit the URL of "GET dealerships" endpoint from IBM Cloud Functions (4 pts)
- https://us-south.functions.appdomain.cloud/api/v1/web/e7d8f3db-0cc6-4f5c-80ef-d9860b3f8248/dealership-package/get-dealership-sequence.json
2. Submit the URL of "GET dealerships" endpoint from IBM Cloud Functions with the state filter added at the end (4 pts)
- https://us-south.functions.appdomain.cloud/api/v1/web/e7d8f3db-0cc6-4f5c-80ef-d9860b3f8248/dealership-package/get_state.json?state=Texas
3. Submit the URL of "GET reviews" endpoint from IBM Cloud Functions with the "dealerId=13" added to the end (4 pts)
- https://us-south.functions.appdomain.cloud/api/v1/web/e7d8f3db-0cc6-4f5c-80ef-d9860b3f8248/dealership-package/get-review.json?dealerId=13

## Screenshots

1. Submit the screenshot with the filename `django_server.jpg` (or a .png file) demonstrating the Django runserver command was running successfully. (4 pts)
2. Submit the screenshot with the filename `contact_us.jpg` (or a .png file) demonstrating the completed “Contact Us” page (4 pts).
3. Submit the screenshot with the filename `about_us.jpg` (or a .png file) demonstrating the completed “About Us” page. (4 pts)
4. Submit the screenshot with the filename `dealerships.jpg` (or a .png file) demonstrating the completed dealership list page (4 pts).
5. Submit the screenshot with the filename `dealerships_filter.jpg` (or a .png file) demonstrating an opened dealership dropdown filter (4 pts).
6. Submit the screenshot with the filename `dealership_details.jpg` (or a .png file) demonstrating the dealership details page with all its reviews (4 pts).
7. Submit the screenshot with the filename `sign_up.jpg` (or a .png file) demonstrating the sign-up page. (4 pts)
8. Submit the screenshot with the filename `login.jpg` (or a .png file) demonstrating the log-in page. (2 pts)
9. Submit the screenshot with the filename `logout.jpg` (or a .png file) demonstrating the log-out button. (2 pts)
10. Submit the screenshot with the filename `dealership_review_submission.jpg` (or a .png file) demonstrating the review submission page. (4 pts)
11. Submit the screenshot with the filename `admin_login.jpg` (or a .png file) demonstrating a logged-in Django admin user. (2 pts)
12. Submit the screenshot with the filename `admin_logout.jpg` (or a .png file) demonstrating the user has been redirected to the Django admin login page. (2 pts)
13. Submit the screenshot with the filename `create_carmake.jpg` (or a .png file) demonstrating the Django admin page to create a new car make and car model. (2 pts)
14. Submit the screenshot with the filename ` updated_carmake_list.jpg` (or a .png file) demonstrating the newly created car make is shown on the car make list. (2 pts)