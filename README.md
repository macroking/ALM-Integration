# ALM-Integration
This project is to integration HP ALM and other test automation frameworks. Still there are many projects that uses HP ALM tool to store their test cases and results in HP Application Life Cycle Management

# Problem statment
Since there are different open source test frameworks, the team always struggle to bring the test cases and test results back to HP ALM. It happened in our team, so I initally created python script for each test framework type and the maintenance went crazy. Finally developed this script to support most of the frequently used test frameworks in web development.

# Environment
** Jenkins / Local Machine **
** Python version < 3 **
** Python Packages **
  1. requests

# What does the script cand do
This script is built primarily to run from Jenkins but it doesn't limit anyone from running it from his/her local machine.
1. Create test cases in HP ALM by parsing your source code
  a. Create folders in HP ALM 
  b. Create test cases in HP ALM
2. Upload the test results in HP ALM by parsing your test results
  a. Create test set folders in HP ALM 
  b. Create test sets in HP ALM
  c. Update test status
  d. Upload the result file

# Supported Frameworks / Tools
1. PROTRACTOR
2. AVA
3. CUCUMBER
4. FRISBY
5. GRAILS
6. KARMA

# Reporting library
Opensource gives us the flexibility to pick from variety of reporting library for any test framework. So this script is limited to the reporting library / output it supports.

| TEST FRAMEWORK | REPORTING LIBRARY           |
-----------------|------------------------------
|  PROTRACTOR    |  jasmine-json-test-reporter |
|  AVA           |  tap-xunit xml              |
|  CUCUMBER      |  cucumberjs json            |
|  FRISBY        |  mocha                      |
|  GRAILS        |  default xml                |
|  KARMA         |  default xml                |

# How to pass input to script?
The input comes from the ./hpqc.config.txt file. "This is hard-coded in the python script". 
