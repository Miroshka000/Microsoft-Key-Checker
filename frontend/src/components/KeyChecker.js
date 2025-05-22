import React, { useState, useEffect, useRef } from 'react';
import { Form, Button, Card, Alert, Spinner, ProgressBar, Badge } from 'react-bootstrap';
import axios from 'axios';


const pulseStyle = {
  animation: 'pulse 1.5s infinite ease-in-out',
  '@keyframes pulse': {
    '0%': { opacity: 0.6 },
    '50%': { opacity: 1 },
    '100%': { opacity: 0.6 }
  }
};


const waitingMessages = [
  'Ожидаем ответ от сервисов Microsoft...',
  'Проверяем статус лицензии на серверах...',
  'Анализируем данные о ключе...',
  'Проверяем региональные ограничения...',
  'Запрашиваем статус активации...',
  'Обрабатываем ответ серверов Microsoft...',
  'Проверяем данные в базе лицензий...',
  'Ожидаем подтверждения от серверов...',
  'Завершение процесса проверки ключа...',
  'Синхронизация с системой лицензий...'
];

const KeyChecker = () => {
  const [key, setKey] = useState('');
  const [region, setRegion] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('');
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [longProcess, setLongProcess] = useState(false);
  const [logEntries, setLogEntries] = useState([]);
  
  
  const checkIdRef = useRef(null);
  const statusPollIntervalRef = useRef(null);
  const longProcessTimeoutRef = useRef(null);
  const isComponentMountedRef = useRef(true);
  const abortControllerRef = useRef(null);
  const retryCountRef = useRef(0);
  const maxRetries = 5;
  const temporaryIdPrefix = 'temp_check_';
  
  
  const addLog = (entry) => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `${timestamp}: ${entry}`;
    console.log(logEntry);
    setLogEntries(prev => [...prev, logEntry]);
  };
  
  
  useEffect(() => {
    isComponentMountedRef.current = true;
    addLog('Компонент KeyChecker инициализирован');
    
    return () => {
      isComponentMountedRef.current = false;
      cleanupResources();
      addLog('Компонент KeyChecker размонтирован');
    };
  }, []);
  
  
  const cleanupResources = () => {
    if (statusPollIntervalRef.current) {
      clearInterval(statusPollIntervalRef.current);
      statusPollIntervalRef.current = null;
      addLog('Опрос статуса остановлен');
    }
    
    if (longProcessTimeoutRef.current) {
      clearTimeout(longProcessTimeoutRef.current);
      longProcessTimeoutRef.current = null;
      addLog('Таймер длительного процесса очищен');
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      addLog('Текущий запрос отменен');
    }
  };
  
  
  const handleCheckResult = (responseData) => {
    addLog(`Обрабатываем результат: ${JSON.stringify(responseData)}`);
    
    
    const normalizedResult = {
      key: responseData.key || key.trim(),
      
      status: responseData.status || (responseData.is_valid ? 'valid' : 'invalid'),
      message: responseData.message || '',
    };
    
    addLog(`Нормализованный результат: ${JSON.stringify(normalizedResult)}`);
    setResult(normalizedResult);
    setProgress(100);
    setLoading(false);
    cleanupResources();
  };
  
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!key.trim()) {
      setError('Введите ключ для проверки');
      return;
    }
    
    setLoading(true);
    setError('');
    setResult(null);
    setProgress(0);
    setStage('');
    setMessage('Инициализация проверки...');
    setLongProcess(false);
    setLogEntries([]);
    retryCountRef.current = 0;
    
    
    const tempId = `${temporaryIdPrefix}${key.trim().replace(/[^a-zA-Z0-9]/g, '')}_${Date.now()}`;
    addLog(`Начинаем проверку ключа: ${key.trim()}, регион: ${region.trim() || 'не указан'}`);
    
    cleanupResources();
    
    
    abortControllerRef.current = new AbortController();
    
    try {
      addLog('Отправка запроса на проверку ключа');
      const response = await axios.post('/api/keys/check', 
        {
          key: key.trim(),
          region: region.trim() || null
        },
        { 
          signal: abortControllerRef.current.signal,
          timeout: 30000 
        }
      );
      
      if (!isComponentMountedRef.current) return;
      
      addLog(`Получен ответ от сервера: ${JSON.stringify(response.data)}`);
      
      
      if (response.data && response.data.check_id) {
        checkIdRef.current = response.data.check_id;
        addLog(`Получен ID проверки: ${response.data.check_id}`);
      } else {
        
        checkIdRef.current = tempId;
        addLog(`ID проверки не получен, используем временный: ${tempId}`);
      }
      
      
      if (response.data) {
        
        if (response.data.status === 'valid' || 
            response.data.status === 'invalid' || 
            response.data.status === 'used' || 
            response.data.status === 'success' ||
            response.data.status === 'error' ||
            typeof response.data.is_valid === 'boolean') {
          
          addLog(`Получен мгновенный результат: ${JSON.stringify(response.data)}`);
          handleCheckResult(response.data);
          return;
        }
      }
      
      
      startStatusPolling();
      
    } catch (error) {
      if (!isComponentMountedRef.current) return;
      
      if (axios.isCancel(error)) {
        addLog('Запрос отменен пользователем');
        return;
      }
      
      console.error('Ошибка при запуске проверки:', error);
      addLog(`Ошибка при запуске проверки: ${error.message}`);
      
      
      if (error.response && error.response.data) {
        addLog(`Получены данные в ответе с ошибкой: ${JSON.stringify(error.response.data)}`);
        
        
        if (error.response.data.status || 
            typeof error.response.data.is_valid === 'boolean' || 
            error.response.data.message) {
          
          handleCheckResult(error.response.data);
          return;
        }
      }
      
      
      const extractedId = extractIdFromError(error, key.trim());
      if (extractedId) {
        checkIdRef.current = extractedId;
        addLog(`Извлечен ID проверки из ошибки: ${extractedId}`);
      } else {
        
        checkIdRef.current = tempId;
        addLog(`Не удалось извлечь ID, используем временный: ${tempId}`);
      }
      
      
      setMessage('Запрос на проверку ключа отправлен, ожидаем результаты...');
      
      
      startStatusPolling();
    }
  };
  
  
  const startStatusPolling = () => {
    
    fetchKeyStatus();
    
    
    if (!statusPollIntervalRef.current) {
      statusPollIntervalRef.current = setInterval(fetchKeyStatus, 2000);
      addLog('Запущен интервал опроса статуса каждые 2 секунды');
      
      
      if (!longProcessTimeoutRef.current) {
        longProcessTimeoutRef.current = setTimeout(() => {
          if (isComponentMountedRef.current) {
            setLongProcess(true);
            setMessage('Проверка может занять до 5 минут. Пожалуйста, подождите...');
            addLog('Активировано уведомление о длительном процессе проверки');
          }
        }, 30000); 
      }
    }
  };
  
  
  const extractIdFromError = (error, keyValue) => {
    
    if (error.response && error.response.data && error.response.data.check_id) {
      return error.response.data.check_id;
    }
    
    
    if (error.config && error.config.url && error.config.url.includes('/keys/status/')) {
      const urlParts = error.config.url.split('/');
      return urlParts[urlParts.length - 1];
    }
    
    
    if (error.message && error.message.includes('timeout') && error.config && error.config.data) {
      try {
        const requestData = JSON.parse(error.config.data);
        if (requestData.key) {
          const cleanKey = requestData.key.replace(/[^a-zA-Z0-9]/g, '');
          return `check_${cleanKey}_${Date.now()}`;
        }
      } catch (e) {}
    }
    
    
    return `check_${keyValue.replace(/[^a-zA-Z0-9]/g, '')}_${Date.now()}`;
  };
  
  
  const fetchKeyStatus = async () => {
    if (!checkIdRef.current || !isComponentMountedRef.current) return;
    
    try {
      addLog(`Запрос статуса проверки ключа: ${checkIdRef.current}`);
      const controller = new AbortController();
      const response = await axios.get(`/api/keys/status/${checkIdRef.current}`, {
        signal: controller.signal,
        timeout: 10000 
      });
      
      if (!isComponentMountedRef.current) return;
      
      
      retryCountRef.current = 0;
      
      const statusData = response.data;
      addLog(`Получен ответ статуса: ${JSON.stringify(statusData)}`);
      
      
      if (statusData.progress !== undefined) {
        setProgress(statusData.progress);
      }
      
      if (statusData.stage) {
        setStage(statusData.stage);
      }
      
      if (statusData.message) {
        setMessage(statusData.message);
      } else if (statusData.stage) {
        setMessage(`Этап: ${statusData.stage} (${statusData.progress}%)`);
      }
      
      
      if ((statusData.status === 'completed' || statusData.status === 'success') && statusData.result) {
        addLog(`Проверка завершена успешно: ${JSON.stringify(statusData.result)}`);
        handleCheckResult(statusData.result);
      } 
      else if (statusData.status === 'error') {
        addLog(`Проверка завершена с ошибкой: ${statusData.error_message || 'Неизвестная ошибка'}`);
        setError(statusData.error_message || 'Произошла ошибка при проверке ключа');
        setLoading(false);
        cleanupResources();
      }
      
      else if (statusData.status === 'not_found' && 
               (checkIdRef.current.includes(temporaryIdPrefix) || checkIdRef.current.includes('temp_'))) {
        
        const keyPart = key.trim().replace(/[^a-zA-Z0-9]/g, '');
        
        if (checkIdRef.current.startsWith(temporaryIdPrefix)) {
          checkIdRef.current = `check_${keyPart}_${Date.now()}`;
          addLog(`ID не найден, переключаемся на: ${checkIdRef.current}`);
        } else if (checkIdRef.current.includes('temp_')) {
          checkIdRef.current = `${temporaryIdPrefix}${keyPart}_${Date.now()}`;
          addLog(`ID не найден, пробуем другой формат: ${checkIdRef.current}`);
        }
      }
    } catch (error) {
      if (!isComponentMountedRef.current || axios.isCancel(error)) {
        return;
      }
      
      retryCountRef.current++;
      console.error('Ошибка при получении статуса:', error);
      addLog(`Ошибка получения статуса (попытка ${retryCountRef.current}/${maxRetries}): ${error.message}`);
      
      
      if (retryCountRef.current >= maxRetries) {
        setMessage('Ожидание ответа сервера. Проверка может занять до 5 минут...');
        retryCountRef.current = 0; 
      }
      
      
    }
  };
  
  
  const handleCancel = () => {
    addLog('Пользователь отменил проверку');
    setLoading(false);
    setError('Проверка была отменена');
    cleanupResources();
  };
  
  
  const getStatusClass = (status) => {
    switch (status) {
      case 'valid':
      case 'success': return 'success';
      case 'used': return 'warning';
      case 'disabled': return 'warning';
      case 'invalid': return 'danger';
      case 'region_error': return 'info';
      default: return 'secondary';
    }
  };
  
  
  const formatKey = (inputKey) => {
    if (!inputKey) return '';
    
    const cleanKey = inputKey.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    
    if (cleanKey.length <= 5) return cleanKey;
    
    let formattedKey = '';
    for (let i = 0; i < cleanKey.length; i += 5) {
      formattedKey += cleanKey.substr(i, 5);
      if (i + 5 < cleanKey.length) formattedKey += '-';
    }
    
    return formattedKey;
  };
  
  
  const handleKeyChange = (e) => {
    const inputValue = e.target.value;
    if (inputValue.length > 5) {
      setKey(formatKey(inputValue));
    } else {
      setKey(inputValue.toUpperCase());
    }
  };

  
  const getDisplayMessage = () => {
    if (message) return message;
    if (stage) return `Этап: ${stage}`;
    return 'Проверка ключа...';
  };

  
  const getStatusText = (status) => {
    switch (status) {
      case 'valid':
      case 'success': return 'Действителен';
      case 'used': return 'Использован';
      case 'disabled': return 'Отключен';
      case 'invalid': return 'Недействителен';
      case 'region_error': return 'Ошибка региона';
      default: return status || 'Неизвестный статус';
    }
  };

  return (
    <div className="key-checker-container">
      <div className="mb-4">
        <h2>Проверка ключа Microsoft</h2>
        <p className="text-muted">Введите ключ и (опционально) регион для проверки</p>
      </div>

      <Form onSubmit={handleSubmit} className="mb-4">
        <Form.Group className="mb-3">
          <Form.Label><strong>Ключ Microsoft</strong></Form.Label>
          <Form.Control 
            type="text" 
            placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" 
            value={key}
            onChange={handleKeyChange}
            disabled={loading}
            className="font-monospace"
          />
          <Form.Text className="text-muted">
            Введите ключ в любом формате, система автоматически его отформатирует.
          </Form.Text>
        </Form.Group>

        <Form.Group className="mb-3">
          <Form.Label><strong>Регион (опционально)</strong></Form.Label>
          <Form.Control 
            type="text" 
            placeholder="Например: US, IN, AR" 
            value={region}
            onChange={(e) => setRegion(e.target.value.toUpperCase())}
            disabled={loading}
            className="font-monospace"
            maxLength={2}
          />
          <Form.Text className="text-muted">
            Если требуется проверить ключ для конкретного региона, введите код страны.
          </Form.Text>
        </Form.Group>

        <div className="d-flex gap-2">
          <Button 
            variant="primary" 
            type="submit" 
            disabled={loading}
            className="px-4"
          >
            {loading ? (
              <>
                <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
                <span className="ms-2">Проверка...</span>
              </>
            ) : 'Проверить ключ'}
          </Button>
          
          {loading && (
            <Button 
              variant="outline-secondary" 
              onClick={handleCancel}
            >
              Отменить
            </Button>
          )}
        </div>
      </Form>

      {loading && (
        <Card className="mb-4 border-primary">
          <Card.Body>
            <div className="d-flex align-items-center mb-2">
              <Spinner animation="border" size="sm" variant="primary" className="me-2" />
              <span>{getDisplayMessage()}</span>
            </div>
            <ProgressBar 
              now={progress} 
              label={`${Math.round(progress)}%`} 
              animated 
              variant={progress < 100 ? "primary" : "success"} 
              style={{ height: '25px' }}
            />
            <div className="text-muted small mt-2">
              <p className="mb-1">
                Проверка может занять до 3 минут в зависимости от загруженности серверов Microsoft.
              </p>
              {longProcess && (
                <p className="text-warning mb-1">
                  <i className="fas fa-exclamation-triangle me-2"></i>
                  Проверка занимает больше времени, чем обычно. Пожалуйста, не закрывайте страницу.
                </p>
              )}
              {error && <Alert variant="warning" className="mt-2 mb-0">{error}</Alert>}
            </div>
          </Card.Body>
        </Card>
      )}

      {error && !loading && <Alert variant="danger">{error}</Alert>}

      {result && (
        <Card border={getStatusClass(result.status)} className="mt-4 shadow-sm">
          <Card.Header as="h5" className={`bg-${getStatusClass(result.status)} text-white`}>
            Результат проверки
          </Card.Header>
          <Card.Body>
            <div className="d-flex align-items-center mb-3">
              <h4 className="mb-0 me-2">Статус:</h4>
              <Badge 
                bg={getStatusClass(result.status)}
                className="fs-6 py-2 px-3"
              >
                {getStatusText(result.status)}
              </Badge>
            </div>

            <div className="key-details p-3 border rounded mb-3 bg-light">
              <div className="mb-2">
                <strong>Ключ:</strong> <span className="font-monospace">{result.key}</span>
              </div>
              
              {result.message && (
                <div className="mb-0">
                  <strong>Сообщение:</strong> {result.message}
                </div>
              )}
            </div>
          </Card.Body>
        </Card>
      )}
    </div>
  );
};

export default KeyChecker; 