const express = require('express');
const gameController = require('../controllers/game.controller');

const router = express.Router();

router.post('/', gameController.createGame);
router.get('/', gameController.getGames);

module.exports = router;
