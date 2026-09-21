import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useSession } from '../hooks/useSession';
import ErrorMessage from './ErrorMessage';
import LoadingSpinner from './LoadingSpinner';

export const StartSessionModal = ({ isOpen, onClose, onSessionStarted }) => {
  const { startSession } = useSession();

  const [games, setGames] = useState([]);
  const [loadingGames, setLoadingGames] = useState(false);
  const [selectedGameId, setSelectedGameId] = useState('');
  
  // Create game toggle & fields
  const [isCreatingGame, setIsCreatingGame] = useState(false);
  const [newGameName, setNewGameName] = useState('');
  const [newGamePlatform, setNewGamePlatform] = useState('PC');

  // Optional session initial details
  const [notes, setNotes] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Load games when modal opens
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    const fetchGames = async () => {
      setLoadingGames(true);
      setError('');
      try {
        const response = await api.get('/games');
        if (isMounted && response && response.games) {
          setGames(response.games);
          if (response.games.length > 0) {
            setSelectedGameId(response.games[0].id);
          } else {
            setIsCreatingGame(true); // If no games exist, default to create mode
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Failed to load games list');
        }
      } finally {
        if (isMounted) setLoadingGames(false);
      }
    };

    fetchGames();
    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCreateGame = async () => {
    if (!newGameName.trim()) {
      setError('Game name is required');
      return null;
    }

    try {
      const response = await api.post('/games', {
        name: newGameName.trim(),
        platform: newGamePlatform.trim() || 'PC'
      });
      if (response && response.success && response.game) {
        setGames((prev) => [response.game, ...prev]);
        setSelectedGameId(response.game.id);
        setIsCreatingGame(false);
        setNewGameName('');
        return response.game.id;
      }
      throw new Error(response.message || 'Failed to create game');
    } catch (err) {
      setError(err.message || 'Failed to create game');
      return null;
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    let gameIdToUse = selectedGameId;

    setSubmitting(true);
    try {
      // If user is adding a new game directly
      if (isCreatingGame) {
        const createdId = await handleCreateGame();
        if (!createdId) {
          setSubmitting(false);
          return;
        }
        gameIdToUse = createdId;
      }

      if (!gameIdToUse) {
        setError('Please select a game to start your session.');
        setSubmitting(false);
        return;
      }

      await startSession({
        gameId: gameIdToUse,
        notes
      });

      if (onSessionStarted) onSessionStarted();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to start gaming session');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Start Gaming Session</h2>
            <p className="modal-subtitle">Choose your game and launch real-time copilot tracking</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <ErrorMessage message={error} />

        {loadingGames ? (
          <LoadingSpinner message="Loading games catalog..." />
        ) : (
          <form className="modal-form" onSubmit={handleSubmit}>
            {!isCreatingGame ? (
              <div className="form-group">
                <div className="label-row">
                  <label htmlFor="select-game">Choose Your Game</label>
                  <button
                    type="button"
                    className="btn-link-action"
                    onClick={() => setIsCreatingGame(true)}
                  >
                    + Add New Game
                  </button>
                </div>
                <select
                  id="select-game"
                  value={selectedGameId}
                  onChange={(e) => setSelectedGameId(e.target.value)}
                  disabled={submitting || games.length === 0}
                >
                  {games.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name} ({g.platform || 'PC'})
                    </option>
                  ))}
                </select>
                {games.length === 0 && (
                  <p className="form-helper">No games found. Please create one below.</p>
                )}
              </div>
            ) : (
              <div className="new-game-box">
                <div className="label-row">
                  <span className="font-semibold text-accent">Register New Game</span>
                  {games.length > 0 && (
                    <button
                      type="button"
                      className="btn-link-action"
                      onClick={() => setIsCreatingGame(false)}
                    >
                      Choose Existing Game
                    </button>
                  )}
                </div>
                <div className="form-group mt-2">
                  <label htmlFor="new-game-name">Game Name</label>
                  <input
                    id="new-game-name"
                    type="text"
                    required
                    placeholder="e.g. Valorant, Apex Legends, CS2"
                    value={newGameName}
                    onChange={(e) => setNewGameName(e.target.value)}
                    disabled={submitting}
                  />
                </div>
                <div className="form-group mt-2">
                  <label htmlFor="new-game-platform">Platform</label>
                  <select
                    id="new-game-platform"
                    value={newGamePlatform}
                    onChange={(e) => setNewGamePlatform(e.target.value)}
                    disabled={submitting}
                  >
                    <option value="PC">PC</option>
                    <option value="PlayStation">PlayStation</option>
                    <option value="Xbox">Xbox</option>
                    <option value="Nintendo Switch">Nintendo Switch</option>
                    <option value="Mobile">Mobile</option>
                  </select>
                </div>
              </div>
            )}

            <div className="form-group mt-2">
              <label htmlFor="session-notes">Session Goal / Notes (Optional)</label>
              <textarea
                id="session-notes"
                rows="2"
                placeholder="e.g. Warm up deathmatch, then 3 competitive matches with Viper"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={submitting}
              />
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={submitting || (!isCreatingGame && games.length === 0)}
              >
                {submitting ? <span className="btn-spinner"></span> : '🎮 Start Session'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default StartSessionModal;
