import React, { useState, useEffect } from 'react';
import { Table, Button, Form, Modal, Alert, Badge } from 'react-bootstrap';
import axios from 'axios';

const AccountManagement = () => {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newAccount, setNewAccount] = useState({ email: '', password: '' });
  const [stats, setStats] = useState(null);

  
  const fetchAccounts = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/accounts/');
      setAccounts(response.data);
      
      
      const statsResponse = await axios.get('/api/accounts/statistics');
      setStats(statsResponse.data);
      
      setError('');
    } catch (err) {
      setError('Ошибка при загрузке аккаунтов');
      console.error('Error fetching accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  
  useEffect(() => {
    fetchAccounts();
  }, []);

  
  const handleAddAccount = async () => {
    try {
      if (!newAccount.email || !newAccount.password) {
        setError('Заполните все поля');
        return;
      }
      
      await axios.post('/api/accounts/', newAccount);
      setNewAccount({ email: '', password: '' });
      setShowAddModal(false);
      fetchAccounts(); 
    } catch (err) {
      setError('Ошибка при добавлении аккаунта');
      console.error('Error adding account:', err);
    }
  };

  
  const handleDeleteAccount = async (accountId) => {
    if (window.confirm('Вы уверены, что хотите удалить этот аккаунт?')) {
      try {
        await axios.delete(`/api/accounts/${accountId}`);
        fetchAccounts(); 
      } catch (err) {
        setError('Ошибка при удалении аккаунта');
        console.error('Error deleting account:', err);
      }
    }
  };

  
  const handleResetAccount = async (accountId) => {
    try {
      await axios.post(`/api/accounts/${accountId}/reset`);
      fetchAccounts(); 
    } catch (err) {
      setError('Ошибка при сбросе счетчика проверок аккаунта');
      console.error('Error resetting account:', err);
    }
  };

  
  const handleResetAllAccounts = async () => {
    if (window.confirm('Вы уверены, что хотите сбросить счетчики всех аккаунтов?')) {
      try {
        await axios.post('/api/accounts/reset-all');
        fetchAccounts(); 
      } catch (err) {
        setError('Ошибка при сбросе счетчиков аккаунтов');
        console.error('Error resetting all accounts:', err);
      }
    }
  };

  
  const getStatusBadge = (status) => {
    switch (status) {
      case 'available': return 'success';
      case 'in_use': return 'primary';
      case 'cooldown': return 'warning';
      case 'error': return 'danger';
      case 'blocked': return 'dark';
      default: return 'secondary';
    }
  };

  return (
    <div>
      <h2>Управление аккаунтами Microsoft</h2>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <p>Аккаунты используются для проверки ключей Microsoft</p>
        <div>
          <Button variant="primary" onClick={() => setShowAddModal(true)} className="me-2">
            Добавить аккаунт
          </Button>
          <Button variant="outline-secondary" onClick={handleResetAllAccounts}>
            Сбросить все счетчики
          </Button>
        </div>
      </div>
      
      {error && <Alert variant="danger">{error}</Alert>}
      
      {stats && (
        <div className="mb-3">
          <Alert variant="info">
            <div className="d-flex justify-content-between">
              <span><strong>Всего аккаунтов:</strong> {stats.total_accounts}</span>
              <span><strong>Доступно:</strong> {stats.available_accounts}</span>
              <span><strong>Используется:</strong> {stats.in_use_accounts}</span>
              <span><strong>Охлаждение:</strong> {stats.cooldown_accounts}</span>
              <span><strong>Ошибки:</strong> {stats.error_accounts + stats.blocked_accounts}</span>
            </div>
          </Alert>
        </div>
      )}
      
      <div className="table-responsive">
        <Table striped bordered hover>
          <thead>
            <tr>
              <th>#</th>
              <th>Email</th>
              <th>Статус</th>
              <th>Проверок</th>
              <th>Последняя проверка</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {accounts.length === 0 && !loading ? (
              <tr>
                <td colSpan="6" className="text-center">Аккаунты не найдены</td>
              </tr>
            ) : (
              accounts.map((account, index) => (
                <tr key={account.id}>
                  <td>{index + 1}</td>
                  <td>{account.email}</td>
                  <td>
                    <Badge bg={getStatusBadge(account.status)}>
                      {account.status === 'available' && 'Доступен'}
                      {account.status === 'in_use' && 'Используется'}
                      {account.status === 'cooldown' && 'Охлаждение'}
                      {account.status === 'error' && 'Ошибка'}
                      {account.status === 'blocked' && 'Заблокирован'}
                    </Badge>
                  </td>
                  <td>{account.checks_count}</td>
                  <td>
                    {account.last_used_at ? new Date(account.last_used_at).toLocaleString() : '-'}
                  </td>
                  <td>
                    <Button 
                      variant="outline-primary" 
                      size="sm" 
                      onClick={() => handleResetAccount(account.id)}
                      className="me-2"
                    >
                      Сбросить
                    </Button>
                    <Button 
                      variant="outline-danger" 
                      size="sm" 
                      onClick={() => handleDeleteAccount(account.id)}
                    >
                      Удалить
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </Table>
      </div>
      
      {}
      <Modal show={showAddModal} onHide={() => setShowAddModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Добавить аккаунт Microsoft</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Email</Form.Label>
              <Form.Control 
                type="email" 
                placeholder="example@example.com" 
                value={newAccount.email}
                onChange={(e) => setNewAccount({...newAccount, email: e.target.value})}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Пароль</Form.Label>
              <Form.Control 
                type="password" 
                placeholder="Пароль" 
                value={newAccount.password}
                onChange={(e) => setNewAccount({...newAccount, password: e.target.value})}
              />
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddModal(false)}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleAddAccount}>
            Добавить
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default AccountManagement; 