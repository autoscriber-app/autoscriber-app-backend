//import {v4 as uuidv4} from 'uuid';
let uuid = require('uuid');


const express = require('express')
const bodyParser = require('body-parser')

const app = express()
const port = 3000
app.use(bodyParser.json)

// Have the correct body parser

/** 
 * SQL SCHEMA 
 * uuid    message    time
 */


/**
 * Sends to DB
 * Assigns UUID
 * 
 * 
 * 
 */
app.post('/add' , (req, res) => {
    if (req.body.uuid == "") {
        req.body.uuid = uuid.v4()
    }
    req.body.message
    req.body.timestamp

    res.send(req.body.uuid)
})

function connect () {
    const password = ""
}



// PART 2 WENDSDAYYY
/**
 * sends response of machine learning (mysql)
 */
app.get ('/notes', (req, res) => {

})

app.listen(port, () => {

})