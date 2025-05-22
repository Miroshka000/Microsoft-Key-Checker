import React, { useState, useEffect } from 'react';
import { Table, Button, Form, Modal, Alert, Badge, Card, Row, Col } from 'react-bootstrap';
import axios from 'axios';

const VPNSettings = () => {
  const [services, setServices] = useState([]);
  const [regions, setRegions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddServiceModal, setShowAddServiceModal] = useState(false);
  const [showAddRegionModal, setShowAddRegionModal] = useState(false);
  const [selectedService, setSelectedService] = useState(null);
  const [vpnStatus, setVpnStatus] = useState(null);
  
  const [newService, setNewService] = useState({
    provider: 'Custom',
    name: '',
    auth_data: {}
  });
  
  const [newRegion, setNewRegion] = useState({
    region_id: '',
    name: '',
    code: ''
  });

  
  const fetchVPNData = async () => {
    try {
      setLoading(true);
      
      
      const servicesResponse = await axios.get('/api/vpn/services');
      setServices(servicesResponse.data);
      
      
      const statusResponse = await axios.get('/api/vpn/status');
      setVpnStatus(statusResponse.data);
      
      setError('');
    } catch (err) {
      setError('Ошибка при загрузке данных VPN');
      console.error('Error fetching VPN data:', err);
    } finally {
      setLoading(false);
    }
  };

  
  const fetchServiceRegions = async (serviceName) => {
    try {
      const response = await axios.get(`/api/vpn/services/${serviceName}/regions`);
      setRegions(response.data);
      setSelectedService(serviceName);
    } catch (err) {
      setError(`Ошибка при загрузке регионов для сервиса ${serviceName}`);
      console.error(`Error fetching regions for service ${serviceName}:`, err);
    }
  };

  
  useEffect(() => {
    fetchVPNData();
  }, []);

  
  const handleAddService = async () => {
    try {
      if (!newService.name) {
        setError('Введите название сервиса');
        return;
      }
      
      await axios.post('/api/vpn/services', newService);
      setNewService({
        provider: 'Custom',
        name: '',
        auth_data: {}
      });
      setShowAddServiceModal(false);
      fetchVPNData(); 
    } catch (err) {
      setError('Ошибка при добавлении VPN сервиса');
      console.error('Error adding VPN service:', err);
    }
  };

  
  const handleAddRegion = async () => {
    try {
      if (!selectedService || !newRegion.region_id || !newRegion.name || !newRegion.code) {
        setError('Заполните все поля');
        return;
      }
      
      await axios.post(`/api/vpn/services/${selectedService}/regions`, newRegion);
      setNewRegion({
        region_id: '',
        name: '',
        code: ''
      });
      setShowAddRegionModal(false);
      fetchServiceRegions(selectedService); 
    } catch (err) {
      setError('Ошибка при добавлении региона');
      console.error('Error adding region:', err);
    }
  };

  
  const handleDeleteService = async (serviceName) => {
    if (window.confirm(`Вы уверены, что хотите удалить сервис ${serviceName}?`)) {
      try {
        await axios.delete(`/api/vpn/services/${serviceName}`);
        fetchVPNData(); 
      } catch (err) {
        setError('Ошибка при удалении VPN сервиса');
        console.error('Error deleting VPN service:', err);
      }
    }
  };

  
  const handleDeleteRegion = async (regionId) => {
    if (window.confirm(`Вы уверены, что хотите удалить этот регион?`)) {
      try {
        await axios.delete(`/api/vpn/services/${selectedService}/regions/${regionId}`);
        fetchServiceRegions(selectedService); 
      } catch (err) {
        setError('Ошибка при удалении региона');
        console.error('Error deleting region:', err);
      }
    }
  };

  
  const handleConnect = async (serviceName, regionCode) => {
    try {
      setLoading(true);
      await axios.post(`/api/vpn/connect/${serviceName}/${regionCode}`);
      fetchVPNData(); 
    } catch (err) {
      setError('Ошибка при подключении к VPN');
      console.error('Error connecting to VPN:', err);
    } finally {
      setLoading(false);
    }
  };

  
  const handleDisconnect = async () => {
    try {
      setLoading(true);
      await axios.post('/api/vpn/disconnect');
      fetchVPNData(); 
    } catch (err) {
      setError('Ошибка при отключении от VPN');
      console.error('Error disconnecting from VPN:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Настройки VPN</h2>
      <p>Управление VPN-соединениями для проверки региональных ключей</p>
      
      {error && <Alert variant="danger">{error}</Alert>}
      
      {}
      {vpnStatus && (
        <Card className="mb-4">
          <Card.Header>Статус VPN</Card.Header>
          <Card.Body>
            <Row>
              <Col md={4}>
                <strong>Статус соединения:</strong> {' '}
                <Badge bg={vpnStatus.connected ? 'success' : 'secondary'}>
                  {vpnStatus.connected ? 'Подключено' : 'Отключено'}
                </Badge>
              </Col>
              <Col md={4}>
                {vpnStatus.current_service && (
                  <div><strong>Текущий сервис:</strong> {vpnStatus.current_service}</div>
                )}
                {vpnStatus.current_region && (
                  <div><strong>Текущий регион:</strong> {vpnStatus.current_region}</div>
                )}
              </Col>
              <Col md={4}>
                {vpnStatus.ip_address && (
                  <div><strong>IP адрес:</strong> {vpnStatus.ip_address}</div>
                )}
                {vpnStatus.connected && (
                  <Button variant="outline-danger" size="sm" onClick={handleDisconnect} disabled={loading}>
                    Отключить VPN
                  </Button>
                )}
              </Col>
            </Row>
          </Card.Body>
        </Card>
      )}
      
      {}
      <div className="mb-4">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h3>VPN сервисы</h3>
          <Button variant="primary" onClick={() => setShowAddServiceModal(true)}>
            Добавить сервис
          </Button>
        </div>
        
        <div className="table-responsive">
          <Table striped bordered hover>
            <thead>
              <tr>
                <th>Название</th>
                <th>Провайдер</th>
                <th>Статус</th>
                <th>Регионы</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {services.length === 0 && !loading ? (
                <tr>
                  <td colSpan="5" className="text-center">Сервисы не найдены</td>
                </tr>
              ) : (
                services.map((service) => (
                  <tr key={service.name}>
                    <td>{service.name}</td>
                    <td>{service.provider}</td>
                    <td>
                      <Badge bg={service.status === 'connected' ? 'success' : 'secondary'}>
                        {service.status === 'connected' ? 'Подключено' : 'Отключено'}
                      </Badge>
                    </td>
                    <td>
                      <Button 
                        variant="link" 
                        size="sm" 
                        onClick={() => fetchServiceRegions(service.name)}
                      >
                        Посмотреть регионы ({service.regions_count})
                      </Button>
                    </td>
                    <td>
                      <Button 
                        variant="outline-danger" 
                        size="sm" 
                        onClick={() => handleDeleteService(service.name)}
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
      </div>
      
      {}
      {selectedService && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h4>Регионы сервиса {selectedService}</h4>
            <Button variant="primary" onClick={() => setShowAddRegionModal(true)}>
              Добавить регион
            </Button>
          </div>
          
          <div className="table-responsive">
            <Table striped bordered hover>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Код</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {regions.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="text-center">Регионы не найдены</td>
                  </tr>
                ) : (
                  regions.map((region) => (
                    <tr key={region.id}>
                      <td>{region.id}</td>
                      <td>{region.name}</td>
                      <td>{region.code}</td>
                      <td>
                        <Badge bg={region.is_active ? 'success' : 'secondary'}>
                          {region.is_active ? 'Активен' : 'Неактивен'}
                        </Badge>
                      </td>
                      <td>
                        <Button 
                          variant="outline-primary" 
                          size="sm" 
                          onClick={() => handleConnect(selectedService, region.code)}
                          className="me-2"
                          disabled={loading || (vpnStatus?.connected && vpnStatus?.current_region === region.code)}
                        >
                          Подключиться
                        </Button>
                        <Button 
                          variant="outline-danger" 
                          size="sm" 
                          onClick={() => handleDeleteRegion(region.id)}
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
        </div>
      )}
      
      {}
      <Modal show={showAddServiceModal} onHide={() => setShowAddServiceModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Добавить VPN сервис</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>Название</Form.Label>
              <Form.Control 
                type="text" 
                placeholder="Название сервиса" 
                value={newService.name}
                onChange={(e) => setNewService({...newService, name: e.target.value})}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Провайдер</Form.Label>
              <Form.Select 
                value={newService.provider}
                onChange={(e) => setNewService({...newService, provider: e.target.value})}
              >
                <option value="NordVPN">NordVPN</option>
                <option value="Surfshark">Surfshark</option>
                <option value="Custom">Пользовательский</option>
              </Form.Select>
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddServiceModal(false)}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleAddService}>
            Добавить
          </Button>
        </Modal.Footer>
      </Modal>
      
      {}
      <Modal show={showAddRegionModal} onHide={() => setShowAddRegionModal(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Добавить регион для {selectedService}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Form.Group className="mb-3">
              <Form.Label>ID региона</Form.Label>
              <Form.Control 
                type="text" 
                placeholder="Например: us, eu, asia" 
                value={newRegion.region_id}
                onChange={(e) => setNewRegion({...newRegion, region_id: e.target.value})}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Название</Form.Label>
              <Form.Control 
                type="text" 
                placeholder="Например: United States, Europe, Asia" 
                value={newRegion.name}
                onChange={(e) => setNewRegion({...newRegion, name: e.target.value})}
              />
            </Form.Group>
            <Form.Group className="mb-3">
              <Form.Label>Код страны</Form.Label>
              <Form.Control 
                type="text" 
                placeholder="Например: US, DE, JP" 
                value={newRegion.code}
                onChange={(e) => setNewRegion({...newRegion, code: e.target.value})}
              />
              <Form.Text className="text-muted">
                Двухбуквенный код страны (ISO 3166-1 alpha-2)
              </Form.Text>
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowAddRegionModal(false)}>
            Отмена
          </Button>
          <Button variant="primary" onClick={handleAddRegion}>
            Добавить
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default VPNSettings; 