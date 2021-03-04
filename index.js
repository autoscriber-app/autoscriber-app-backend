const express = require("express");
const mysql = require("mysql");
const bodyParser = require("body-parser");
const uuid = require("uuid");
const cors = require("cors");

const app = express();
const port = 3000;
const con = mysql.createConnection({
  host: "localhost",
  user: "youruser",
  password: "yourpass",
  database: "db",
});

app.use(bodyParser.json());
app.use(cors());

/**
 * Sends to MySQL DB
 * Assigns UUID if user doesn't have one
 * Sends UUID back to user if user doesn't have one
 */
app.post("/add", (req, res) => {
  if (req.body.uuid == "") {
    req.body.uuid = uuid.v4();
    res.send(req.body.uuid);
  } else {
    res.sendStatus(res.statusCode);
  }

  const sqlInsert = `INSERT INTO blobs VALUES ("${req.body.uuid}", "${req.body.message}", "${req.body.timestamp}", "0")`;
  con.query(sqlInsert, (err, result) => {
    if (err) throw err;
    console.log(req.body.uuid + ": Message inserted to 'blobs' table");
  });
});

/**
 * Needs UUID
 * returns all the processed data
 * TODO:Gives processed data
 */
app.get("/processed", (req, res) => {
  const sqlSelect = `SELECT processed_message FROM processed_notes WHERE uuid = "${req.body.uuid}"`;
  con.query(sqlSelect, (err, result) => {
    if (err) throw err;
    res.send(result);
  });
});

/**
 * TODO: Indicates that User is finished with session and deletes it
 */
app.delete("/user", (req, res) => {
  const tables = ["blobs", "processed_notes"];
  con.query(
    `DELETE from blobs WHERE uuid = "${req.body.uuid}";`,
    (err, result) => {
      if (err) throw err;
    }
  );
  con.query(
    `DELETE from processed_notes WHERE uuid = "${req.body.uuid}";`,
    (err, result) => {
      if (err) throw err;
    }
  );

  console.log("Notes deleted. User session closed.");
  res.sendStatus(res.statusCode);
});

/**
 * TODO:ML asks for list of jobs. Returns a list filled with JSONs:
 * [{"message": "blob1", "time": XXXXXXX, blob2, blob3 ...]
 */
app.get("/jobs", (req, res) => {
  const sqlSelect = `SELECT message, time FROM blobs WHERE uuid = "${req.body.uuid}" ORDER BY time`;
  con.query(sqlSelect, (err, result) => {
    if (err) throw err;
    res.send(result);
  });
});

/**
 * TODO:ML gives all the processed blobs in json
 *
 * UUID: XXX
 * Message: ZZZ
 */
app.post("/jobs", (req, res) => {
  const sqlInsert = `INSERT INTO processed_notes VALUES ("${req.body.uuid}", "${req.body.message}")`;
  con.query(sqlInsert, (err, result) => {
    if (err) throw err;
    console.log("Message inserted to 'processed_notes' table");
  });
  res.sendStatus(res.statusCode);
});

//TODO: Helper funtions to database Cleanupa
app.listen(port, () => {
  console.log("Server is running on port 3000...");
  con.connect(async (err) => {
    if (err) throw err;
    console.log("MySQL connection established!");
    await createTables();
    console.log("Tables are ready!");
  });
});

function createTables() {
  // Create table for incoming text blobs
  const createBlobs =
    "CREATE TABLE IF NOT EXISTS blobs (uuid char(38) NOT NULL, message LONGTEXT NOT NULL, time INT NOT NULL, processed BOOLEAN NOT NULL, PRIMARY KEY (uuid, time)) DEFAULT CHARSET=utf8;";
  con.query(createBlobs, (err, result) => {
    if (err) throw err;
  });

  // Create table for processed blobs
  const createProcessedBlobs =
    "CREATE TABLE IF NOT EXISTS processed_notes (uuid char(32) NOT NULL, message LONGTEXT NOT NULL, PRIMARY KEY (uuid)) DEFAULT CHARSET=utf8;";
  con.query(createProcessedBlobs, (err, result) => {
    if (err) throw err;
  });
}
