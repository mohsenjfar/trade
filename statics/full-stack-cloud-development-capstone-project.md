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