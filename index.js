//import {v4 as uuidv4} from 'uuid';
let uuid = require('uuid');

 
const express = require('express')
const bodyParser = require('body-parser')

const app = express()
const port = 3000
app.use(bodyParser.json)

// Have the correct body parser
/**
 * TODO:Create DB with the schema
 * 
 * DB is for storing ML stuff
 * 
 * uuid          procssedMessage
 */
/** 
 * SQL SCHEMA 
 * uuid    message    time
 */


/**
 * Sends to DB
 * Assigns UUID
 * Gives Timestamp and sends to DB
 */
app.post('/add' , (req, res) => {
    if (req.body.uuid == "") {
        req.body.uuid = uuid.v4()
    }
    req.body.message
    req.body.timestamp

    res.send(req.body.uuid)
})
/**
 * Needs UUID 
 * returns all the prossed data
 * TODO:Gives prossesd data
 */
app.get('/get', (req, res) => {

})

/**
 * TODO: Indicates that User is finished with session and deletes it
 */
app.delete('/delete', (req, res) => {

})

function connect () {
    const password = ""
}

// PART 2 WENDSDAYYY
/**
 * TODO:ML asks for list of jobs. Returns a json fild with 
 * UUID : [blob1, blob2, blob3 ...]
 */
app.get ('/jobs', (req, res) => {

})

/**
 * TODO:ML gives all the prossesd blobs in json
 * 
 * UUID : Message
 */
app.post( '/jobs', (req, res) => {

})


//TODO: Helper funtions to database Cleanupa
app.listen(port, () => {

})