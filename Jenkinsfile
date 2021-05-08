pipeline {
    agent any

    environment {
        SQL_PASS = credentials('autoscriber_mysql')
        SQL_USER = credentials('autoscriber_mysql_user')
        CONTAINER_NAME = "autoscriber-container"
        IMAGE_NAME = "autoscriber-image"
    }

    stages {
        stage ('Checkout') {
            steps {
                checkout([$class: 'GitSCM', branches: [[name: '*/master']], extensions: [], userRemoteConfigs: [[credentialsId: 'github-ssh-key', url: 'git@github.com:autoscriber-app/autoscriber-app-backend.git']]])
            }
        }
        stage('Build') {
            steps {
                //  Building new image
                sh 'docker image build -t $IMAGE_NAME .'
                sh 'docker image tag $IMAGE_NAME:latest $IMAGE_NAME:$BUILD_NUMBER'
                echo "Image built :P"
            }
        }
        stage('Deploy') {
            steps {
                script{
                    //https://github.com/talha22081992/flask-docker-app-jenkins-pipeline/blob/master/Jenkinsfile
                    //sh 'BUILD_NUMBER = ${BUILD_NUMBER}'
                    if (BUILD_NUMBER == "84") {
                        sh 'docker run --name $CONTAINER_NAME -d -e SQL_USER=$SQL_USER -e SQL_PASS=$SQL_PASS --net=host $IMAGE_NAME'
                    }
                    else {
                        sh 'docker stop $CONTAINER_NAME'
                        sh 'docker rm $CONTAINER_NAME'
                        sh 'docker run --restart unless-stopped --name $CONTAINER_NAME -d -e SQL_USER=$SQL_USER -e SQL_PASS=$SQL_PASS --net=host $IMAGE_NAME'
                    }
                    sh 'echo "Latest image/code deployed"'
                }
            }
        }
    }
}
