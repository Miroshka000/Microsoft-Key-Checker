import React, { useState, useEffect } from 'react';
import { Form, Button, Card, Alert, Spinner, ProgressBar, Table } from 'react-bootstrap';
import axios from 'axios';

const BatchCheck = () => {
  const [keys, setKeys] = useState('');
  const [file, setFile] = useState(null);
  const [region, setRegion] = useState('');
  const [loading, setLoading] = useState(false);
  const [batchId, setBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [pollingInterval, setPollingInterval] = useState(null);

  
  const handleReset = () => {
    setKeys('');
    setFile(null);
    setRegion('');
    setError('');
    setBatchId(null);
    setBatchStatus(null);
    setResults([]);
    
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
  };

  
  const handleFileChange = (e) => {
    if (e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setKeys(''); 
    }
  };

  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!keys.trim() && !file) {
      setError('Введите ключи или загрузите файл');
      return;
    }

    setLoading(true);
    setError('');
    setBatchId(null);
    setBatchStatus(null);
    setResults([]);

    try {
      let response;
      
      if (file) {
        
        const formData = new FormData();
        formData.append('file', file);
        if (region.trim()) {
          formData.append('region', region.trim());
        }
        
        response = await axios.post('/api/keys/upload', formData);
      } else {
        
        const keysList = keys.trim().split('\n').map(key => ({
          key: key.trim(),
          region: region.trim() || null
        })).filter(k => k.key);

        response = await axios.post('/api/keys/check-batch', {
          keys: keysList,
          regions: region.trim() ? Array(keysList.length).fill(region.trim()) : null
        });
      }

      setBatchId(response.data.batch_id);
      
      
      const interval = setInterval(() => {
        fetchBatchStatus(response.data.batch_id);
      }, 2000);
      
      setPollingInterval(interval);
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка при отправке ключей');
      console.error('Error submitting keys:', err);
      setLoading(false);
    }
  };

  
  const fetchBatchStatus = async (id) => {
    try {
      const response = await axios.get(`/api/keys/batch/${id}`);
      setBatchStatus(response.data);
      
      if (response.data.status === 'completed') {
        
        fetchBatchResults(id);
        
        
        if (pollingInterval) {
          clearInterval(pollingInterval);
          setPollingInterval(null);
        }
        
        setLoading(false);
      }
    } catch (err) {
      console.error('Error fetching batch status:', err);
      if (pollingInterval) {
        clearInterval(pollingInterval);
        setPollingInterval(null);
      }
      setLoading(false);
      setError('Ошибка при получении статуса проверки');
    }
  };

  
  const fetchBatchResults = async (id) => {
    try {
      const response = await axios.get(`/api/keys/batch/${id}/results`);
      setResults(response.data);
    } catch (err) {
      console.error('Error fetching batch results:', err);
      setError('Ошибка при получении результатов проверки');
    }
  };

  
  const handleExport = async (format, status) => {
    if (!batchId) return;
    
    try {
      window.open(`/api/keys/batch/${batchId}/export/${format}/${status}`);
    } catch (err) {
      console.error('Error exporting results:', err);
      setError('Ошибка при экспорте результатов');
    }
  };

  
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  return (
    <div>
      <h2>Пакетная проверка ключей</h2>
      <p>Загрузите файл с ключами или введите их вручную</p>

      <Form onSubmit={handleSubmit} className="mb-4">
        <Form.Group className="mb-3">
          <Form.Label>Выберите файл с ключами</Form.Label>
          <Form.Control 
            type="file" 
            accept=".txt,.csv"
            onChange={handleFileChange}
            disabled={loading}
          />
          <Form.Text className="text-muted">
            Поддерживаемые форматы: TXT (по одному ключу на строку), CSV (с колонками "key" и "region").
          </Form.Text>
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Или введите ключи вручную</Form.Label>
          <Form.Control 
            as="textarea" 
            rows={5}
            placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"
            value={keys}
            onChange={(e) => setKeys(e.target.value)}
            disabled={loading || file !== null}
          />
          <Form.Text className="text-muted">
            Введите по одному ключу в каждой строке.
          </Form.Text>
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label>Регион (опционально)</Form.Label>
          <Form.Control 
            type="text" 
            placeholder="Например: US, IN, AR" 
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            disabled={loading}
          />
          <Form.Text className="text-muted">
            Если требуется проверить ключи для конкретного региона, введите код страны.
          </Form.Text>
        </Form.Group>

        <div className="d-flex gap-2">
          <Button variant="primary" type="submit" disabled={loading}>
            {loading ? (
              <>
                <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
                <span className="ms-2">Отправка...</span>
              </>
            ) : 'Проверить ключи'}
          </Button>
          
          <Button variant="secondary" onClick={handleReset} disabled={loading}>
            Сбросить
          </Button>
        </div>
      </Form>

      {error && <Alert variant="danger">{error}</Alert>}

      {batchStatus && (
        <Card className="mb-4">
          <Card.Header>Статус проверки</Card.Header>
          <Card.Body>
            <Card.Title>
              Batch ID: {batchId}
            </Card.Title>
            <Card.Text>
              <strong>Статус:</strong> {batchStatus.status === 'completed' ? 'Завершено' : 'В процессе'}<br />
              <strong>Всего ключей:</strong> {batchStatus.total_keys}<br />
              <strong>Обработано:</strong> {batchStatus.processed_keys}<br />
            </Card.Text>
            
            <ProgressBar 
              now={batchStatus.progress * 100} 
              label={`${Math.round(batchStatus.progress * 100)}%`} 
              className="mb-3"
              variant="primary"
            />
            
            {batchStatus.status === 'completed' && (
              <div className="d-flex gap-2 flex-wrap">
                <Button variant="outline-primary" size="sm" onClick={() => handleExport('csv', 'all')}>
                  Экспортировать все (CSV)
                </Button>
                <Button variant="outline-success" size="sm" onClick={() => handleExport('txt', 'valid')}>
                  Экспортировать валидные (TXT)
                </Button>
              </div>
            )}
          </Card.Body>
        </Card>
      )}

      {results.length > 0 && (
        <Card>
          <Card.Header>
            <div className="d-flex justify-content-between align-items-center">
              <span>Результаты проверки</span>
              <small className="text-muted">Найдено: {results.length}</small>
            </div>
          </Card.Header>
          <Card.Body className="p-0">
            <div className="table-responsive">
              <Table striped bordered hover>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Ключ</th>
                    <th>Статус</th>
                    <th>Регион</th>
                    <th>Сообщение</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result, index) => {
                    const statusClass = 
                      result.status === 'valid' ? 'table-success' :
                      result.status === 'used' ? 'table-warning' :
                      result.status === 'invalid' ? 'table-danger' :
                      result.status === 'region_error' ? 'table-info' : '';
                      
                    return (
                      <tr key={index} className={statusClass}>
                        <td>{index + 1}</td>
                        <td>{result.key}</td>
                        <td>{result.status.toUpperCase()}</td>
                        <td>{result.region_used || '-'}</td>
                        <td>{result.error_message || '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          </Card.Body>
        </Card>
      )}
    </div>
  );
};

export default BatchCheck;