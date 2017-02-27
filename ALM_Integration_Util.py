'''
This file contains the method necessary to parse
output file from different testing frameworks
and write the results back to HP ALM.
'''
import re
import json
import datetime
import time
import sys
import os, fnmatch
from os import listdir
from os.path import isfile, join
from xml.etree.ElementTree import Element, SubElement, tostring, parse
import glob
from requests.auth import HTTPBasicAuth
import requests

ALM_USER_NAME = ""
ALM_PASSWORD = ""
ALM_DOMAIN = ""
ALM_URL = ""
AUTH_END_POINT = ALM_URL + "authentication-point/authenticate"
QC_SESSION_END_POINT = ALM_URL + "rest/site-session"
QC_LOGOUT_END_POINT = ALM_URL + "authentication-point/logout"
ALM_MIDPOINT = "rest/domains/" + ALM_DOMAIN + "/projects/"
PATH_SEP = os.path.sep

# Report paths for different frameworks
GRAILS_REPORT_PATH = './target/test-reports'
AVA_REPORT_PATH = './functional-test-results.xml'
FRISBY_REPORT_PATH = './out/api-tests/report.xml'
CUCUMBER_REPORT_PATH = './cucumber-test-results.html.json'
PROTRACTOR_REPORT_PATH = './combined_result.json'
KARMA_REPORT_PATH = './out/unit-test-results.xml'

def remove_special_char(str_input):
    '''
        Function    :   remove_special_char
        Description :   Function to remove non-acceptable characters
        Parameters  :   1 parameter
                        str_input   -   input string
    '''
    return re.sub('[^A-Za-z0-9\\s_-]+', '', str_input).strip()

def create_key_value(obj_json):
    '''
        Function    :   create_key_value
        Description :   Function to generate key-value pair from json
        Parameters  :   1 parameter
                        obj_json   -   JSON Object
    '''
    final_dic = {}
    for elem in obj_json:
        if len(elem['values']) >= 1:
            if 'value' in elem['values'][0]:
                final_dic[elem["Name"]] = elem["values"][0]['value']
    return final_dic

def get_field_value(obj, field_name):
    '''
        Function    :   get_field_value
        Description :   Find the value of matching json key
        Parameters  :   2 Parameters
                        obj         -   JSON object
                        field_name  -   JSON KEY
    '''
    for field in obj:
        if field['Name'] == field_name:
            return field['values'][0]['value']
    return None

def generate_xml_data(inputdata):
    '''
        Function    :   generateXMLData
        Description :   Generate an xml string
        Parameters  :   Dictionary of variable
    '''
    root = Element('Entity')
    root.set('Type', inputdata['Type'])
    inputdata.pop('Type')
    childs = SubElement(root, 'Fields')

    for key, value in inputdata.iteritems():
        child1 = SubElement(childs, 'Field')
        child1.set('Name', key)
        child2 = SubElement(child1, 'Value')
        child2.text = value
    return tostring(root)

# ALM Class begins
class ALM(object):
    '''
        Nothing
    '''
    def __init__(self, test_plan_path, test_set_path, test_set_name):
        self.test_plan_path = test_plan_path
        self.test_set_path = test_set_path
        self.test_set_name = test_set_name
        self.all_test_instance = None
        self.all_tests = None
        self.cookies = dict()
        self.alm_session = requests.Session()
        self.parser_temp_dic = {}
        self.alm_session.headers.update({'cache-control': "no-cache"})

    def alm_login(self):
        """
            Function    :   alm_login
            Description :   Authenticate user
            Parameters  :   global parameter
                            alm_username     -   ALM User
                            alm_password     -   ALM Password
        """
        response = self.alm_session.post(AUTH_END_POINT,
                                         auth=HTTPBasicAuth(ALM_USER_NAME, ALM_PASSWORD))
        if response.status_code == 200:
            response = self.alm_session.post(QC_SESSION_END_POINT)
            if response.status_code == 200 | response.status_code == 201:
                print "ALM Authentication successful"
            else:
                print "Error: ", response.staus_code
        else:
            print "Error: ", response.staus_code
        self.alm_session.headers.update({'Accept':'application/json',
                                         'Content-Type': 'application/xml'})
        return

    def alm_logout(self):
        '''
            Function    :   alm_logout
            Description :   terminate user session
            Parameters  :   No Parameters
        '''
        response = self.alm_session.post(QC_LOGOUT_END_POINT)
        print "Logout successful", response.headers.get('Expires'), response.status_code
        return

    def get_all_test_fromplan(self, test_plan_details):
        '''
            Function    :   get_all_test_fromplan
            Description :   get all the test cases from plan
            Input       :   test_plan_hierarchy path
        '''
        payload = {"query": "{test-folder.hierarchical-path['" +
                            test_plan_details["hierarchical-path"] + "*'"\
                        "]}", "fields": "id,name,steps", "page-size": 5000}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/tests", params=payload)
        self.all_tests = json.loads(response.text)
        return

    def get_all_test_instance_fromlab(self, test_set_id):
        '''
            Function    :   get_all_test_instance_fromlab
            Description :   get all the test instances from lab
            Input       :   test_set_id
        '''
        str_api = "test-instances"
        payload = {"query": "{cycle-id['" + test_set_id + "']}", "fields": "test-id",
                   "page-size": 5000}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/" + str_api, params=payload)
        self.all_test_instance = json.loads(response.text)
        return

    def find_test_plan_folder(self, overridepath=None):
        '''
            Function    :   find_test_plan_folder
            Description :   This sends a couple of http request and authenticate the user
            Parameters  :   1 Parameter
                            test_set_path    -   ALM test set path
        '''
        _test_plan_path = self.test_plan_path
        if  overridepath:
            _test_plan_path = overridepath
        print "test plan folder", _test_plan_path
        json_str = json.loads(self.find_folder_id(_test_plan_path.split("\\"), "test-folders",
                                                  2, "id,hierarchical-path"))
        if 'entities' in json_str:
            return create_key_value(json_str['entities'][0]['Fields'])
        else:
            return create_key_value(json_str['Fields'])

    def find_test_set_folder(self):
        '''
            Function    :   find_test_set_folder
            Description :   This sends a couple of http request and authenticate the user
            Parameters  :   1 Parameter
                            test_set_path    -   ALM test set path
        '''
        json_str = json.loads(self.find_folder_id(self.test_set_path.split("\\"), "test-set-folders"
                                                  , 0, "id"))
        if 'entities' in json_str:
            return create_key_value(json_str['entities'][0]['Fields'])['id']
        else:
            return create_key_value(json_str['Fields'])['id']

    def find_folder_id(self, arrfolder, str_api, parent_id, fields):
        '''
            Function    :   find_folder_id
            Description :   This sends a couple of http request and authenticate the user
            Parameters  :   1 Parameter
                            test_set_path    -   ALM test set path
        '''
        for foldername in arrfolder:
            payload = {"query": "{name['" + foldername + "'];parent-id[" + str(parent_id) + "]}",
                       "fields": fields}
            response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/" + str_api, params=payload)
            obj = json.loads(response.text)
            if obj["TotalResults"] >= 1:
                parent_id = get_field_value(obj['entities'][0]['Fields'], "id")
                # print("folder id of " + foldername + " is " + str(parent_id))
            else:
                # print("Folder " + foldername + " does not exists")
                inputdata = dict()
                inputdata['Type'] = str_api[0:len(str_api) - 1]
                inputdata['name'] = foldername
                inputdata['parent-id'] = str(parent_id)
                data = generate_xml_data(inputdata)
                response = self.alm_session.post(ALM_URL + ALM_MIDPOINT + "/" + str_api, data=data)
                obj = json.loads(response.text)
                if response.status_code == 200 | response.status_code == 201:
                    parent_id = get_field_value(obj['Fields'], "id")
                    # print("folder id of " + foldername + " is " + str(parent_id))
        return response.text

    def find_test_case(self, str_test_name, parent_id, str_api):
        '''
            Function    :   Find_test_case
            Description :   Check if test exists, else create one in test plan
        '''
        test_details = dict({"id": "", "steps": ""})
        payload = {"query": "{name['" + str(str_test_name) + "'];parent-id["
                            + str(parent_id) + "]}", "fields": "id,steps"}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/" + str_api, params=payload)
        obj = json.loads(response.text)
        if obj["TotalResults"] >= 1:
            test_details['id'] = get_field_value(obj['entities'][0]['Fields'], "id")
            test_details['steps'] = get_field_value(obj['entities'][0]['Fields'], "steps")
        else:
            data = self.create_test_case(str_test_name, parent_id)
            response = requests.post(ALM_URL + ALM_MIDPOINT + "/" + str_api, data=data)
            obj = json.loads(response.text)
            if response.status_code == 200 | response.status_code == 201:
                test_details['id'] = get_field_value(obj['Fields'], "id")
                test_details['steps'] = get_field_value(obj['Fields'], "steps")
        return test_details

    def create_test_case(self, str_test_name, parent_id):
        '''
            Function    :   create_test_cases
            Description :   Create test in test plan if not exists
            Parameter   :   s
        '''
        inputdata = dict()
        inputdata['Type'] = 'test'
        inputdata['name'] = str_test_name
        inputdata['parent-id'] = str(parent_id)
        inputdata['subtype-id'] = 'MANUAL'
        inputdata['user-04'] = ALM_USER_NAME
        inputdata['user-03'] = 'Y'
        return generate_xml_data(inputdata)

    def find_test_set(self, test_set_folder_id, str_api):
        '''
            Function    :   Find_test_set
            Description :   Check if Test Set exist, else create one in Test Lab
            Parameters  :   test_set_folder_id  -   Test Lab Folder ID
                            str_api             -   test-sets
                            testsetname         -   Name of the test set
        '''
        payload = {"query": "{name['" + self.test_set_name + "'];parent-id[" +
                            str(test_set_folder_id) + "]}", "fields": "id"}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/" + str_api, params=payload)
        obj = json.loads(response.text)
        parent_id = None
        if obj["TotalResults"] >= 1:
            parent_id = get_field_value(obj['entities'][0]['Fields'], "id")
            # print("test set id of " + testSetName + " is " + str(parent_id))
        else:
            # print("Folder " + testSetName + " does not exists")
            inputdata = dict()
            inputdata['Type'] = str_api[0:len(str_api) - 1]
            inputdata['name'] = self.test_set_name
            inputdata['parent-id'] = str(test_set_folder_id)
            inputdata['subtype-id'] = 'hp.qc.test-set.default'
            data = generate_xml_data(inputdata)
            response = self.alm_session.post(ALM_URL + ALM_MIDPOINT + "/" + str_api, data=data)
            obj = json.loads(response.text)
            if response.status_code == 200 | response.status_code == 201:
                parent_id = get_field_value(obj['Fields'], "id")
                # print("test set id of " + testSetName + " is " + str(parent_id))
        return parent_id

    def create_run_instance(self, test_set_id):
        '''
            Function    :   create_run_instance
            Description :   Create new run instances
            Parameters  :   No input parameter
        '''
        str_api = "test-instances"
        fields = "id,test-id,test-config-id,cycle-id"
        payload = {"query": "{cycle-id['" + test_set_id + "']}", "fields": fields,
                   "page-size": 5000}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/" + str_api, params=payload)
        obj = json.loads(response.text)

        run_instance_post = "<Entities>"
        for entity in obj["entities"]:
            run_name = re.sub('[-:]', '_',
                              'automation_' + datetime.datetime.fromtimestamp(time.time()).strftime(
                                  '%Y-%m-%d %H:%M:%S'))
            temp_map = create_key_value(entity["Fields"])
            _test_id = int(temp_map['test-id'])
            self.parser_temp_dic[_test_id]['testcycl-id'] = temp_map['id']
            self.parser_temp_dic[_test_id]['test-config-id'] = temp_map['test-config-id']
            self.parser_temp_dic[_test_id]['test-id'] = temp_map['test-id']
            self.parser_temp_dic[_test_id]['cycle-id'] = temp_map['cycle-id']
            # parser_temp_dic[int(temp_map['test-id'])]['status'].sort()
            status = "Passed"
            if 'Failed' in self.parser_temp_dic[int(temp_map['test-id'])]['status']:
                status = 'Failed'
            self.parser_temp_dic[int(temp_map['test-id'])]['final-status'] = status

            inputdata = dict()
            inputdata['Type'] = 'run'
            inputdata['name'] = run_name
            inputdata['owner'] = ALM_USER_NAME
            inputdata['test-instance'] = str(1)
            inputdata['testcycl-id'] = str(temp_map['id'])
            inputdata['cycle-id'] = str(temp_map['cycle-id'])
            inputdata['status'] = 'Not Completed'
            inputdata['test-id'] = temp_map['test-id']
            inputdata['subtype-id'] = 'hp.qc.run.MANUAL'
            data = generate_xml_data(inputdata)
            run_instance_post = run_instance_post + data

        self.bulk_operation("runs", run_instance_post + "</Entities>", True, "POST")
        return

    def update_run_instance(self, test_set_id):
        '''
            Function    :   update_run_instance
            Description :   Update the test status in run instances
            Parameters  :   No input parameter
        '''
        fields = "id,test-id"
        payload = {"query": "{cycle-id['" + test_set_id + "']}", "fields": fields,
                   "page-size": 5000}
        response = self.alm_session.get(ALM_URL + ALM_MIDPOINT + "/runs", params=payload)
        obj = json.loads(response.text)

        run_instance_put = "<Entities>"
        for entity in obj["entities"]:
            if len(entity["Fields"]) != 1:
                temp_map = create_key_value(entity["Fields"])
                self.parser_temp_dic[int(temp_map['test-id'])]['run-id'] = temp_map['id']
                inputdata = dict()
                inputdata['Type'] = 'run'
                inputdata['id'] = str(temp_map['id'])
                intermediate_ = self.parser_temp_dic[int(temp_map['test-id'])]['testcycl-id']
                inputdata['testcycl-id'] = str(intermediate_)
                inputdata['status'] = self.parser_temp_dic[int(temp_map['test-id'])]['final-status']
                data = generate_xml_data(inputdata)
                run_instance_put = run_instance_put + data

        self.bulk_operation("runs", run_instance_put + "</Entities>", True, "PUT")
        return

    def upload_result_file(self, test_set_id, report_file):
        '''
            Function    :   upload_result_file
            Description :   Upload test result to ALM
        '''
        payload = open(report_file, 'rb')
        headers = {}
        headers['Content-Type'] = "application/octet-stream"
        headers['slug'] = "test-results" + report_file[report_file.rfind(".")+1: ]
        response = self.alm_session.post(ALM_URL + ALM_MIDPOINT + "/test-sets/" +
                                         str(test_set_id) + "/attachments/",
                                         headers=headers, data=payload)
        if not (response.status_code == 200 or response.status_code == 201):
            print "Attachment step failed!", response.text, response.url, response.status_code
        return


    def bulk_operation(self, str_api, data, isbulk, request_type):
        '''
            Function    :   Post Test Case / Test Instance
            Description :   Generic function to post multiple entities.
            Parameters  :   3 parameters
                            str_api          -   End point name
                            data             -   Actual data to post
                            isbulk           -   True or False
        '''
        response = None
        headers = {}
        try:
            if isbulk:
                headers['Content-Type'] = "application/xml;type = collection"
            if request_type == 'POST':
                response = self.alm_session.post(ALM_URL + ALM_MIDPOINT + "/" + str_api, data=data,
                                                 headers=headers)
            elif request_type == 'PUT':
                response = self.alm_session.put(ALM_URL + ALM_MIDPOINT + "/" + str_api, data=data,
                                                headers=headers)
        except Exception as err:
            print err
        if response.status_code == 200 | response.status_code == 201:
            return response.text
        return response

# End of class ALM

# Spec parser class begins
class SpecParser(ALM):
    '''
        Parse source files and create test case in HP ALM.
    '''
    def __init__(self, test_plan_path, test_set_path, test_set_name, test_type, spec_root):
        self.test_type = test_type
        self.spec_root = spec_root
        super(SpecParser, self).__init__(test_plan_path, test_set_path, test_set_name)
        self.spec_tree = {}
        self.testcase_list = {}
        self.spec_file_name = None
        self._temp_test_case_list = []
        self.testcase_data = ""

    @staticmethod
    def find_files(directory, pattern):
        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename.lower(), pattern.lower()):
                    filename = os.path.join(root, basename)
                    yield filename

    def parse_spec_file(self):
        '''
            Function    :   parse_spec_file
            Description :   Find all the spec files inside the root folder
            Parameters  :   No parameter
        '''
        #search_patterns = {'PROTRACTOR': 'spec.js', 'KARMA': 'spec.js'}
        try:
            if self.test_type.upper() == "PROTRACTOR" or self.test_type.upper() == "KARMA"\
               or self.test_type.upper() == "AVA" or self.test_type.upper() == "FRISBY":
                pattern = 'spec.js'
            elif self.test_type.upper() == "GRAILS":
                pattern = "spec.groovy"
            elif self.test_type.upper() == "CUCUMBER":
                pattern = ".feature"
            self._temp_test_case_list = [x['Fields'][1]['values'][0]['value'].strip() for x in self.all_tests['entities']]
            for name in SpecParser.find_files(self.spec_root, '*' + pattern):
                self.spec_file_name = name[name.rfind(PATH_SEP) + 1:name.rfind(".")]
                if pattern in name.lower():
                    with open(name) as file_:
                        self.testcase_list[self.spec_file_name] = {'file_path': name, 'values': []}
                        content = file_.readlines()
                        if self.test_type.upper() == "FRISBY":
                            temp_ = [elem for elem in content if 'frisby.create' in elem]
                            for temp_i in temp_:
                                if re.match("(\\s{1,}|)frisby\\.create", temp_i):
                                    dtext = re.sub("frisby?create", "", remove_special_char(temp_i))
                                    self.addhierarchy(dtext.strip())
                        elif self.test_type.upper() == "CUCUMBER":
                            temp_ = [elem for elem in content if 'Scenario' in elem]
                            for temp_i in temp_:
                                if re.match("^\\s{1,}Scenario(| Outline)\\s{0,}:", temp_i):
                                    dtext = re.sub("\\s{0,}(Scenario|Scenario Outline)", "",
                                                    remove_special_char(temp_i))
                                    self.addhierarchy(dtext.strip())
                        elif self.test_type.upper() == "GRAILS":
                            temp_ = [elem for elem in content if 'void' in elem or 'def' in elem]
                            for temp_i in temp_:
                                if re.match("^\\s{4}(void|def)", temp_i):
                                    dtext = re.sub("(^def|void)", "", remove_special_char(temp_i))
                                    if dtext.strip() != 'setup':
                                        self.addhierarchy(dtext.strip())
                        elif self.test_type.upper() == "PROTRACTOR"\
                             or self.test_type.upper() == "KARMA":
                            temp_ = [elem for elem in content\
                                    if 'describe(' in elem or 'it(' in elem]
                            for temp_i in temp_:
                                if 'describe' in temp_i:
                                    if re.match("^(|x)describe", temp_i):
                                        # Concatenate spec file name to the describe block
                                        dtext = re.sub("(^describe| function$)", "",
                                                       remove_special_char(temp_i))
                                        self.addremove_node(1, dtext)
                                    else:
                                        for i in range(1, 6):
                                            if re.match("^\\s{" + str(i * 4) + "}(|x)describe", temp_i):
                                                dtext = re.sub("(^describe| function$)", "",
                                                               remove_special_char(temp_i))
                                                self.addremove_node(1 + i, dtext)
                                                break
                                elif 'it' in temp_i:
                                    if re.match("^\\s{1,}(|x)it", temp_i):
                                        ttext = re.sub("(^it| function$)", "",
                                                       remove_special_char(temp_i))
                                        self.addhierarchy(ttext)
                        elif self.test_type.upper() == "AVA":
                            temp_ = [elem for elem in content if 'test' in elem]
                            for temp_i in temp_:
                                if re.match("^test\(", temp_i):
                                    dtext = re.sub("(^test| function.*)", "", remove_special_char(temp_i))
                                    if dtext.strip() != 'setup':
                                        self.addhierarchy(dtext.strip())
                        else:
                            print " Unknow automation framework type"
        except Exception as e:
            print e
        finally:
            for testcase in self.testcase_list:
                if self.testcase_list[testcase]['values']:
                    folder_name = self.testcase_list[testcase]['file_path'].replace(self.spec_root, "")
                    print "file path", self.testcase_list[testcase]['file_path'], " root", self.spec_root
                    print "folder name", folder_name
                    folder_name = folder_name.replace("/", "\\")
                    print "second folder name", folder_name
                    folder_details = self.find_test_plan_folder(self.test_plan_path + folder_name[:folder_name.rfind(".")])
                    for tests in self.testcase_list[testcase]['values']:
                        self.testcase_data += self.create_test_case(tests, folder_details['id'])
        return

    def addhierarchy(self, str_test_name):
        '''
            Function    :   addhierarchy
            Description :   Concatenate Describe and it block strings
            Parameters  :   global parameter
                            str_test_name     -   String inside it block
        '''
        temp_s = ""
        for _ in list(self.spec_tree):
            if self.spec_tree[_].startswith("xdescribe")  or str_test_name.startswith("xit"):
                return
            temp_s += self.spec_tree[_] + "_"
            # Karma test report does not concatenate the parent describes. overriding here
        if self.test_type.upper() == "KARMA" :
            temp_s = ""
        str_test_name = temp_s + str_test_name.strip()
        if not str_test_name in self._temp_test_case_list:
            if not str_test_name in self.testcase_list[self.spec_file_name]['values']:
                self.testcase_list[self.spec_file_name]['values'].append(str_test_name)
        return

    def addremove_node(self, strkey, strvalue):
        '''
            Function    :   addremove_node
            Description :   Add hierarchy to stack
            Parameters  :   global parameter
                            strKey     -   Integer -Hierarchy
                            strValue   -   String inside the describe block
        '''
        if strkey in self.spec_tree:
            for item in list(self.spec_tree):
                if item >= strkey:
                    self.spec_tree.pop(item)
        self.spec_tree[strkey] = strvalue.strip()
        return

    def get_spec_name(self, strtestname):
        '''
            Function    :   addremove_node
            Description :   Add hierarchy to stack
            Parameters  :   global parameter
                            strKey     -   Integer -Hierarchy
                            strValue   -   String inside the describe block
        '''
        spec_name = ""
        try:
            combined = ",".join(self.testcase_list).replace("_", " ")
            temp_s2 = combined.find(strtestname)
            temp_s3 = combined[:temp_s2].rfind(",")
            temp_s4 = combined[temp_s3 + 1:].find(",")
            if temp_s4 == -1:
                temp_s4 = temp_s3 + 256
            else:
                temp_s4 += temp_s3 + 1
            temp_s2 = combined[temp_s3 + 1: temp_s4]
            spec_name = temp_s2[temp_s2.rfind("/")+1:temp_s2.find("=")]
            testname = self.testcase_list[combined.split(",").index(temp_s2)]
            strtestname = testname[testname.find("=") + 1 : ]
        except Exception as e:
            print e
        return spec_name, strtestname
# End of spec parser

class TestFramework(SpecParser):
    '''
        Nothing
    '''
    def __init__(self, test_plan_path, test_set_path, test_set_name, test_type, spec_root, onlycreatetestcase=False):
        self.onlycreatetestcase = onlycreatetestcase
        super(TestFramework, self).__init__(test_plan_path, test_set_path, test_set_name,
                                            test_type, spec_root)
        self.test_order = 0
        self.test_instance_data = ""
        self.report_file = None
        self.test_set_id = None

    def parse_result(self):
        '''
            Function    :   parse_result
            Description :   Parse result file
            Parameters  :   No Parameters
        '''

        # Get all the test id's if test plan folder exists already
        test_plan_details = self.find_test_plan_folder()
        self.get_all_test_fromplan(test_plan_details)

        # Parse the source code to find new test cases
        self.parse_spec_file()
        if self.testcase_data:
            res = self.bulk_operation("tests", "<Entities>" + self.testcase_data +
                                      "</Entities>", True, "POST")
            self.scrub_response(json.loads(res), ['id', 'name'])

        if onlycreatetestcase:
            return

        folder_id = self.find_test_set_folder()
        print "Get all test cases from ", folder_id
        self.test_set_id = self.find_test_set(folder_id, "test-sets")

        # Get all test instance if test set exists already
        print "Get all test instance from ", self.test_set_id
        self.get_all_test_instance_fromlab(self.test_set_id)

        self.report_file = self.parse_output()
        self.bulk_operation("test-instances", "<Entities>" + self.test_instance_data +
                            "</Entities>", True, "POST")
        self.create_run_instance(self.test_set_id)
        self.update_run_instance(self.test_set_id)
        try:
            self.upload_result_file(self.test_set_id, self.report_file)
        except Exception as err:
            print "Unable to process attachment", err
        return

    def scrub_response(self, obj, key_fields):
        '''
            Will add doc string later.
        '''
        for  entity in obj['entities']:
            for  _ in reversed(entity['Fields']):
                if  not _['Name']  in key_fields:
                    entity['Fields'].remove(_)
        for _temp in obj['entities']:
            self.all_tests['entities'].append(_temp)
        return


    def parse_output(self):

        '''
            Nothing
        '''
        if self.test_type.upper() == "FRISBY":
            return self.parse_mocha_karma(FRISBY_REPORT_PATH)
        elif self.test_type.upper() == "CUCUMBER":
            return self.parse_cucumber()
        elif self.test_type.upper() == "GRAILS":
            return self.parse_grails()
        elif self.test_type.upper() == "KARMA":
            return self.parse_mocha_karma(KARMA_REPORT_PATH)
        elif self.test_type.upper() == "PROTRACTOR":
            return self.parse_protractor()
        elif self.test_type.upper() == "AVA":
            return self.parse_ava()
        else:
            print " Unknow automation framework type"
        return

    def check_test_instance_exists(self, test_name, isfailed):
        '''
            Nothing
        '''
        # Check if the test case already exits in test plan
        output_test_name = re.sub('[^A-Za-z0-9\\s]+', '', test_name).strip()
        test_details = self.test_exists(output_test_name, self.all_tests)

        test_case_exists = True
        if len(test_details) == 0:
            test_case_exists = False

        if test_case_exists:
            self.parser_temp_dic[int(test_details['id'])] = {'status': []}

        # Test case status
        status = 'Passed'
        if isfailed is not None:
            status = 'Failed'

        # Check if test instance exists in test set
        test_instance_exists = True
        if test_case_exists:
            self.parser_temp_dic[int(test_details['id'])]['status'].append(status)
            if len(self.test_exists(test_details['id'], self.all_test_instance)) == 0:
                test_instance_exists = False

        if test_instance_exists is False and test_case_exists is True:
            self.test_order += 1
            data = self.create_test_instance(self.test_order, self.test_set_id,
                                             test_details['id'])
            self.test_instance_data += data

    def test_exists(self, str_test_name, obj_json):
        '''
            Function    :   test_exists
            Description :   Check if given test case exists, if not create one
            Parameters  :   2 parameters
                            str_test_name   -   End point name
                            obj_json        -   json data
        '''
        str_exists = ''
        for test in obj_json['entities']:
            almtestname = re.sub('[^A-Za-z0-9\\s_]+', '', test['Fields'][1]['values'][0]['value']
                                 .replace("_", " ")).strip()
            if almtestname == str_test_name:
                return create_key_value(test['Fields'])
        return str_exists

    def create_test_instance(self, test_order, test_set_id, test_id):
        '''
            Function    :   create_test_instance
            Description :   Copy test cases from plan to lab for execution
            Parameter   :   test_set_id
        '''
        inputdata = dict()
        inputdata['Type'] = 'test-instance'
        inputdata['owner'] = ALM_USER_NAME
        inputdata['test-order'] = str(test_order)
        inputdata['cycle-id'] = str(test_set_id)
        inputdata['test-id'] = str(test_id)
        inputdata['subtype-id'] = 'hp.qc.test-instance.MANUAL'
        template_in = json.dumps({u'Fields': [{u'values': [{u'value': u'DUMMMY'}],
                                    u'Name': u'id'}, {u'values': [{u'value':
                                    unicode(test_id)}],
                                    u'Name': u'test-id'}],
                                    u'Type': u'test-instance'})
        self.all_test_instance['entities'].append(json.loads(template_in))
        return generate_xml_data(inputdata)

    def parse_mocha_karma(self, test_result_file):
        '''
            Nothing
        '''
        root = None
        print "inside karma method", test_result_file
        try:
            root = parse(test_result_file).getroot()
        except Exception as err:
            print "File Not found error: {0}".format(err)
        if root is not None:
            for testcase in root.findall(".//testcase"):
                isfailed = None
                testname = testcase.attrib['name']
                isfailed = testcase.find('failure')
                self.check_test_instance_exists(testname, isfailed)
        return test_result_file

    def parse_cucumber(self):
        '''
            Nothing. Yet to find way to bring that here....
        '''
        try:
            obj_file = open(CUCUMBER_REPORT_PATH, 'r')
        except Exception as err:
            print "File not found error: {0}".format(err)
            return
        obj = json.load(obj_file)
        for feature in obj:
            for scenario in feature['elements']:
                if scenario["type"] == "background":
                    continue
                isfailed = None
                if int(scenario['failed']) <> 0:
                    isfailed = True
                self.check_test_instance_exists(scenario['name'], isfailed)
        return CUCUMBER_REPORT_PATH
    def parse_grails(self):
        '''
            Nothing
        '''
        for file_ in listdir(GRAILS_REPORT_PATH):
            if isfile(join(GRAILS_REPORT_PATH, file_)):
                test_result_file = join(GRAILS_REPORT_PATH, file_)
                root = None
                try:
                    root = parse(test_result_file).getroot()
                except Exception as err:
                    print "File Not found error: {0}".format(err)
                if root is not None:
                    for testcase in root.findall(".//testcase"):
                        isfailed = None
                        testname = testcase.attrib['name']
                        isfailed = testcase.find('failure')
                        self.check_test_instance_exists(testname, isfailed)
        return

    def parse_protractor(self):
        '''
            Nothing
        '''
        try:
            obj_file = open(PROTRACTOR_REPORT_PATH, 'r')
        except Exception as err:
            print "File not found error: {0}".format(err)
            return
        obj = json.load(obj_file)
        for spec in obj:
            for testsuite in spec:
                if len(spec[testsuite]['specs']) < 1:
                    continue
                for test in spec[testsuite]['specs']:
                    isfailed = None
                    if test['status'].lower() <> 'passed':
                        isfailed = True
                    self.check_test_instance_exists(test['fullName'], isfailed)
        return PROTRACTOR_REPORT_PATH

    def parse_ava(self):
        '''
            Nothing
        '''
        test_result_file = AVA_REPORT_PATH
        try:
            root = parse(test_result_file).getroot()
        except Exception as err:
            print "File Not found error: {0}".format(err)
        if root is not None:
            for testcase in root.findall(".//testsuite"):
                isfailed = None
                tempstring = testcase.attrib['name']
                testname = tempstring[tempstring.find(u"\u203A") + 1:len(tempstring)].strip()
                failure = int(testcase.attrib['failures'])
                errors = int(testcase.attrib['errors'])
                if failure > 0 or errors > 0:
                    isfailed = True
                self.check_test_instance_exists(testname, isfailed)
        return AVA_REPORT_PATH

# End of class Test TestFramework

def main(strenv, build_number, onlycreatetestcase):
    '''
        Nothing
    '''
    fname = './hpqc.conf.txt'
    alm_config = {
        'ALM_URL': '', 'ALM_URL': '', 'ALM_USER_NAME': '', 'ALM_PASSWORD': '', 'ALM_DOMAIN': '',
        'GIT_TEST_LOC': '', 'ALM_PROJECT': '', 'TEST_PLAN_PATH' : '',
        'TEST_SET_PATH' : '', 'TEST_PLAN_FOLDERS': '', 'TEST_SET_FOLDERS' : '',
        'TEST_SET_NAME': '', 'TEST_TYPE': '', 'ASSIGNMENT_GROUP': ''}
    with open(fname, 'r') as file:
        contents = file.readlines()
    for content in contents:
        content = content.split("=")
        if len(content) == 2:
            alm_config[content[0]] = content[1].strip()

    global ALM_MIDPOINT
    ALM_MIDPOINT = ALM_MIDPOINT + alm_config['ALM_PROJECT']
    ALM_URL =  alm_config['ALM_URL']
    ALM_USER_NAME =  alm_config['ALM_USER_NAME']
    ALM_PASSWORD =  alm_config['ALM_PASSWORD']
    ALM_DOMAIN =  alm_config['ALM_DOMAIN']
    
    spec_folder_path = alm_config['GIT_TEST_LOC'].split(",")
    test_plan_folders = alm_config['TEST_PLAN_FOLDERS'].split(",")
    test_set_folders = alm_config['TEST_SET_FOLDERS'].split(",")
    test_set_names = alm_config['TEST_SET_NAME'].split(",")
    test_types = alm_config['TEST_TYPE'].split(",")
    cnt = len(test_types)
    for _ in range(cnt):
        try:
            specparser = TestFramework(alm_config['TEST_PLAN_PATH'].strip() + "\\" +
                                       test_plan_folders[_].strip(),
                                       alm_config['TEST_SET_PATH'].strip() + "\\" +
                                       test_set_folders[_].strip(),
                                       test_set_names[_].strip()+"_"+strenv+"_"+str(build_number)+
                                       "_"+datetime.date.today().strftime('%b-%d-%Y'),
                                       test_types[_].strip(),
                                       spec_folder_path[_], onlycreatetestcase)
            specparser.alm_login()
            specparser.parse_result()
        finally:
            specparser.alm_logout()

if __name__ == "__main__":
    if len(sys.argv) - 1 != 3:
        print('Build number is required.You have passed :', str(sys.argv), 'arguments.')
    else:
        build_number = sys.argv[1]
        strenv = sys.argv[2]
        onlycreatetestcase = sys.argv[3]
        main(build_number, strenv, onlycreatetestcase)
