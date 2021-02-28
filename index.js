//import {v4 as uuidv4} from 'uuid';
let uuid = require('uuid');
console.log('Your UUID is: ' + uuid.v4());

const express = require('express')
const app = express()
const port = 3000


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
    req.body.uuid // IF doesn't assingn it one 
    req.body.message

    // put  it to database
    req.body.timestamp
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